"""Tool interface: the exact surface a local model gets to touch SAPHIR.

Works with native function calling (OpenAI-compatible servers, Ollama) and
with prompt-only models via ``PromptedToolsBackend``. Never lets the model
invent a result: every answer is a JSON tool result.
"""
from __future__ import annotations

import json

from .core import HarnessError, HarnessTimeout, SaphirHarness

MAX_SLOTS_JSON = 120  # leave room for envelope + AEAD tag inside the 200B cap


def _spec(name: str, description: str, properties: dict | None = None,
          required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
                "additionalProperties": False,
            },
        },
    }


class ToolBridge:
    """Maps model tool calls onto one harness instance."""

    def __init__(self, harness: SaphirHarness, outbound_intents=()):
        self.harness = harness
        self.outbound_intents = tuple(outbound_intents)

    # ---- schema ----
    def specs(self) -> list[dict]:
        hints = ", ".join(self.outbound_intents) or "ask saphir_status first"
        return [
            _spec(
                "saphir_status",
                "Report the SAPHIR link state, peer identity, local capabilities, "
                "capability verdict, and byte counters. Call this before acting if "
                "you are unsure whether the link is paired.",
            ),
            _spec(
                "saphir_pair",
                "Establish an authenticated, encrypted SAPHIR session with the peer. "
                "Auto-called by saphir_send_task/saphir_serve when needed, so call it "
                "directly only to pair early or to surface pairing errors.",
            ),
            _spec(
                "saphir_send_task",
                "Send one encrypted structured TASK to the paired peer and return its "
                f"RESULT. Outbound intents for this agent: {hints}. Slots must be a "
                "small JSON object: the whole frame is capped at 200 bytes.",
                {
                    "intent": {"type": "string",
                               "description": "Structured intent, e.g. hotel.book"},
                    "slots": {"type": "object",
                              "description": "Small JSON object of slot names to values"},
                    "ontology": {"type": "string",
                                 "description": "Optional ontology tag; defaults to the "
                                                "harness configuration"},
                },
                ["intent", "slots"],
            ),
            _spec(
                "saphir_serve",
                "Service side: wait for one inbound encrypted TASK, execute the local "
                "handler, and reply with an encrypted RESULT. Returns the task and "
                "result, or a refusal when the intent is outside the allow-list.",
                {"timeout_s": {"type": "number",
                               "description": "Seconds to wait for a task (default 30)"}},
            ),
            _spec(
                "saphir_audit",
                "Return the human-readable sidecar transcript: frame types, directions, "
                "sizes, and decrypted task/result summaries.",
                {"limit": {"type": "integer",
                           "description": "Number of trailing entries (default 20)"}},
            ),
            _spec(
                "saphir_close",
                "Send BYE and close the link. Call only when the conversation is over.",
            ),
        ]

    # ---- dispatch ----
    def call(self, name: str, arguments: dict | None = None) -> dict:
        """Execute one tool call. Always returns a JSON-serializable dict."""
        args = arguments or {}
        if not isinstance(args, dict):
            return {"ok": False, "error": "arguments must be a JSON object"}
        try:
            return self._dispatch(name, args)
        except HarnessTimeout as e:
            return {"ok": False, "error": f"timeout: {e}"}
        except (HarnessError, ValueError, TypeError, KeyError, OSError) as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    def dispatch(self, name: str, arguments: dict | None = None) -> str:
        """Tool result as the JSON string a chat API expects."""
        return json.dumps(self.call(name, arguments), default=str)

    def _dispatch(self, name: str, args: dict) -> dict:
        h = self.harness
        if name == "saphir_status":
            return {"ok": True, **h.status()}

        if name == "saphir_pair":
            return {"ok": True, **h.pair()}

        if name == "saphir_send_task":
            intent = args.get("intent")
            slots = args.get("slots", {})
            if not isinstance(intent, str) or not intent:
                return {"ok": False, "error": "intent must be a non-empty string"}
            if not isinstance(slots, dict):
                return {"ok": False, "error": "slots must be an object"}
            size = len(json.dumps(slots))
            if size > MAX_SLOTS_JSON:
                return {"ok": False,
                        "error": f"slots encode to {size}B; keep them under "
                                 f"{MAX_SLOTS_JSON}B so the frame fits 200B"}
            return h.send_task(intent, slots, args.get("ontology"))

        if name == "saphir_serve":
            timeout = args.get("timeout_s", 30)
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                return {"ok": False, "error": "timeout_s must be a positive number"}
            return h.serve_one(timeout=float(timeout))

        if name == "saphir_audit":
            limit = args.get("limit", 20)
            if not isinstance(limit, int) or limit < 1:
                limit = 20
            return {"ok": True, "entries": h.audit_tail(limit),
                    "transcript": h.transcript()}

        if name == "saphir_close":
            return {"ok": True, **h.close()}

        return {"ok": False, "error": f"unknown tool {name!r}",
                "available": [s["function"]["name"] for s in self.specs()]}
