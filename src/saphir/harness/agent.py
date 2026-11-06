"""Agent loop: a local model drives SAPHIR through tools.

The loop is deliberately plain (plan -> tool call -> observe -> answer) so it
works with small local models. All effects go through ``ToolBridge``; the
model never touches session state, keys, or the wire directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .backends import ChatBackend, ModelTurn
from .core import SaphirHarness
from .tools import ToolBridge


class AgentError(Exception):
    pass


SYSTEM = """You are {agent_id}, a local AI agent bridged to the SAPHIR protocol.
Your peer is another AI agent reachable over an authenticated, encrypted,
low-bandwidth channel ({transport} transport, {role} role).

Rules:
1. Act only through tools. Never claim a task succeeded unless a tool result says "ok": true.
2. TASK frames are capped at 200 bytes. Keep slot values short and omit unnecessary fields.
3. Do not invent intents or capabilities. {intent_rule}
4. If a tool returns an error, report it plainly. Retry at most once, and only after changing the input.
5. Do not reveal keys or raw ciphertext. Summaries and audit entries are fine.
6. When the goal is complete, answer the user in one or two short sentences.

Local capabilities (offers): {offers}
Outbound intent for this run: {need}
Ontology: {ontology}
"""


@dataclass
class AgentRun:
    text: str
    steps: int = 0
    tool_trace: list = field(default_factory=list)
    messages: list = field(default_factory=list)

    @property
    def paired(self) -> bool:
        return any(t["tool"] == "saphir_pair" or
                   (t["tool"] in ("saphir_send_task", "saphir_serve") and
                    t["result"].get("ok")) for t in self.tool_trace)


class SaphirAgent:
    """A model + a harness + the tool bridge, in a bounded loop."""

    def __init__(self, backend: ChatBackend, harness: SaphirHarness,
                 outbound_intents=(), max_steps: int = 8, max_tokens: int = 400,
                 system: str | None = None):
        self.backend = backend
        self.harness = harness
        self.bridge = ToolBridge(harness, outbound_intents=outbound_intents)
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.system = system or self._system()

    def _system(self) -> str:
        h = self.harness
        need = h.cfg.need
        if need:
            intent_rule = f"Use {need!r} for this run; other intents are out of scope."
        elif h.cfg.offers:
            intent_rule = ("You are the service side. Wait for inbound tasks with "
                           "saphir_serve rather than initiating tasks.")
        else:
            intent_rule = "Check saphir_status before choosing an intent."
        return SYSTEM.format(
            agent_id=h.cfg.agent_id,
            transport=h.transport.name,
            role=h.cfg.role,
            intent_rule=intent_rule,
            offers=", ".join(h.cfg.offers) or "(none advertised)",
            need=need or "(none)",
            ontology=h.cfg.ontology,
        )

    def run(self, goal: str) -> AgentRun:
        messages = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": goal},
        ]
        trace = []
        for step in range(1, self.max_steps + 1):
            turn = self.backend.chat(messages, tools=self.bridge.specs(),
                                     max_tokens=self.max_tokens)
            if not isinstance(turn, ModelTurn):
                raise AgentError("backend returned a non-ModelTurn value")
            if not turn.tool_calls:
                return AgentRun(text=turn.text or "", steps=step, tool_trace=trace,
                                messages=messages)
            messages.append(self._assistant_message(turn))
            for call in turn.tool_calls:
                result = self.bridge.call(call.name, call.arguments)
                trace.append({"step": step, "tool": call.name,
                              "args": call.arguments, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id or f"call_{step}",
                    "name": call.name,
                    "content": json.dumps(result, default=str),
                })
        return AgentRun(text="[stopped: tool-call limit reached]",
                        steps=self.max_steps, tool_trace=trace, messages=messages)

    @staticmethod
    def _assistant_message(turn: ModelTurn) -> dict:
        return {
            "role": "assistant",
            "content": turn.text or "",
            "tool_calls": [c.wire() for c in turn.tool_calls],
        }
