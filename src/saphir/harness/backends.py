"""Local-model backends: Ollama, OpenAI-compatible servers, prompt-only models.

Everything speaks one tiny canonical message format (OpenAI-shaped), so the
agent loop is model-runtime agnostic. No third-party HTTP client is required:
the standard library is enough for these endpoints.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

from ..llm import LLMBackend


class BackendError(Exception):
    pass


@dataclass
class ToolCall:
    name: str
    arguments: dict = field(default_factory=dict)
    id: str = ""

    def wire(self) -> dict:
        return {"id": self.id, "type": "function",
                "function": {"name": self.name,
                             "arguments": json.dumps(self.arguments)}}


@dataclass
class ModelTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: dict | None = None


class ChatBackend:
    """Minimal protocol: canonical messages in, one turn out."""

    name = "base"
    supports_tools = True

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             max_tokens: int = 400) -> ModelTurn:
        raise NotImplementedError


def _json_post(url: str, payload: dict, headers: dict | None = None,
               timeout: float = 120.0) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json",
                                          **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise BackendError(f"{url} -> HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise BackendError(f"cannot reach {url}: {e.reason}") from e
    except (TimeoutError, OSError) as e:
        raise BackendError(f"{url} timed out or failed: {e}") from e


def _coerce_args(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else {}
        except ValueError:
            return {}
    return {}


class OpenAICompatBackend(ChatBackend):
    """llama.cpp server, LM Studio, vLLM, LocalAI, text-generation-webui, ...

    ``base_url`` includes the version: http://localhost:8080/v1
    """

    name = "openai-compatible"

    def __init__(self, model: str, base_url: str = "http://localhost:8080/v1",
                 api_key: str = "", temperature: float = 0.0,
                 timeout: float = 120.0):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout

    @staticmethod
    def _messages(messages: list[dict]) -> list[dict]:
        # Strict servers reject unknown fields (e.g. Ollama's tool_name).
        out = []
        for m in messages:
            item = {"role": m.get("role"), "content": m.get("content", "")}
            if m.get("tool_calls"):
                item["tool_calls"] = m["tool_calls"]
            if m.get("tool_call_id"):
                item["tool_call_id"] = m["tool_call_id"]
            out.append(item)
        return out

    def chat(self, messages, tools=None, max_tokens=400) -> ModelTurn:
        payload = {
            "model": self.model,
            "messages": self._messages(messages),
            "temperature": self.temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        data = _json_post(f"{self.base_url}/chat/completions", payload, headers,
                          self.timeout)
        try:
            msg = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as e:
            raise BackendError(f"unexpected chat response: {str(data)[:300]}") from e
        calls = []
        for i, c in enumerate(msg.get("tool_calls") or []):
            fn = c.get("function") or {}
            calls.append(ToolCall(name=fn.get("name", ""),
                                  arguments=_coerce_args(fn.get("arguments")),
                                  id=c.get("id") or f"call_{i}"))
        return ModelTurn(text=msg.get("content") or "", tool_calls=calls, raw=msg)


class OllamaChatBackend(ChatBackend):
    """Native Ollama /api/chat with tool calling. Default: qwen2.5:1.5b."""

    name = "ollama"

    def __init__(self, model: str = "qwen2.5:1.5b",
                 host: str = "http://localhost:11434", temperature: float = 0.0,
                 timeout: float = 120.0):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    @staticmethod
    def _messages(messages: list[dict]) -> list[dict]:
        out = []
        for m in messages:
            role = m.get("role")
            if role == "assistant" and m.get("tool_calls"):
                calls = []
                for c in m["tool_calls"]:
                    args = c["function"]["arguments"]
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except ValueError:
                            args = {}
                    calls.append({"function": {"name": c["function"]["name"],
                                               "arguments": args}})
                out.append({
                    "role": "assistant",
                    "content": m.get("content") or "",
                    "tool_calls": calls,
                })
            elif role == "tool":
                item = {"role": "tool", "content": m.get("content", "")}
                if m.get("name"):
                    item["tool_name"] = m["name"]
                out.append(item)
            else:
                out.append({"role": role, "content": m.get("content", "")})
        return out

    def chat(self, messages, tools=None, max_tokens=400) -> ModelTurn:
        payload = {
            "model": self.model,
            "messages": self._messages(messages),
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": max_tokens},
        }
        if tools:
            payload["tools"] = tools
        data = _json_post(f"{self.host}/api/chat", payload, None, self.timeout)
        msg = data.get("message") or {}
        calls = []
        for i, c in enumerate(msg.get("tool_calls") or []):
            fn = c.get("function") or {}
            calls.append(ToolCall(name=fn.get("name", ""),
                                  arguments=_coerce_args(fn.get("arguments")),
                                  id=c.get("id") or f"call_{i}"))
        return ModelTurn(text=msg.get("content") or "", tool_calls=calls, raw=msg)


class ScriptedBackend(ChatBackend):
    """Deterministic turns for demos/tests: {"tool": ..., "args": ...} or {"text": ...}."""

    name = "scripted"

    def __init__(self, turns: list):
        self.turns = [self._turn(t) for t in turns]
        self.calls: list[dict] = []

    @staticmethod
    def _turn(t):
        if isinstance(t, ModelTurn):
            return t
        if isinstance(t, str):
            return ModelTurn(text=t)
        if "tool" in t or "name" in t:
            return ModelTurn(tool_calls=[ToolCall(
                name=t.get("tool") or t.get("name"),
                arguments=t.get("args") or t.get("arguments") or {},
                id=t.get("id") or "")])
        return ModelTurn(text=t.get("text", ""))

    def chat(self, messages, tools=None, max_tokens=400) -> ModelTurn:
        self.calls.append({"messages": messages, "tools": tools})
        if not self.turns:
            return ModelTurn(text="[scripted: out of turns]")
        return self.turns.pop(0)


TOOL_INSTRUCTIONS = """You can act through these tools. Reply with exactly one
JSON object per turn and nothing else.
To call a tool: {"tool": "<name>", "args": {<arguments>}}
To answer the user: {"final": "<short answer>"}

Tools:
%s
"""


class PromptedToolsBackend(ChatBackend):
    """Adapter for local models with no native function calling.

    Wraps any text-completion function (system, user) -> str, injects the tool
    schema as text, and parses the ``{"tool": ..., "args": ...}`` convention.
    """

    name = "prompted"
    supports_tools = False

    def __init__(self, complete: Callable[[str, str], str],
                 max_tokens: int = 400):
        self._complete = complete
        self.max_tokens = max_tokens

    @classmethod
    def from_llm(cls, backend: LLMBackend, max_tokens: int = 400):
        return cls(lambda system, user: backend.complete(
            system, user, max_tokens=max_tokens), max_tokens=max_tokens)

    def _prompt(self, messages: list[dict], tools: list[dict] | None) -> tuple[str, str]:
        system = "\n".join(m.get("content", "") for m in messages
                           if m.get("role") == "system")
        if tools:
            rendered = "\n".join(
                f"- {t['function']['name']}: {t['function']['description']}"
                for t in tools)
            system += "\n\n" + TOOL_INSTRUCTIONS % rendered
        lines = []
        for m in messages:
            role = m.get("role")
            if role == "system":
                continue
            if role == "tool":
                lines.append(f"TOOL RESULT ({m.get('name', 'tool')}): {m.get('content', '')}")
            elif role == "assistant" and m.get("tool_calls"):
                for c in m["tool_calls"]:
                    lines.append(f"ASSISTANT CALL: {c['function']['name']} "
                                 f"{c['function']['arguments']}")
            else:
                lines.append(f"{role.upper()}: {m.get('content', '')}")
        return system, "\n".join(lines)

    @staticmethod
    def _parse(text: str) -> ModelTurn:
        candidates = [text.strip()]
        candidates += re.findall(r"\{.*\}", text, re.DOTALL)
        for c in candidates:
            try:
                obj = json.loads(c)
            except (ValueError, TypeError):
                continue
            if not isinstance(obj, dict):
                continue
            name = obj.get("tool") or obj.get("name")
            if isinstance(name, str) and name:
                args = obj.get("args") or obj.get("arguments") or {}
                return ModelTurn(tool_calls=[ToolCall(name=name,
                                                      arguments=_coerce_args(args))])
            if "final" in obj:
                return ModelTurn(text=str(obj["final"]))
        return ModelTurn(text=text.strip())

    def chat(self, messages, tools=None, max_tokens=None) -> ModelTurn:
        system, user = self._prompt(messages, tools)
        return self._parse(self._complete(system, user))
