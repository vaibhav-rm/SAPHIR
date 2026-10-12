"""Real-AI integration: LLMs plan structured tasks and speak the English phase.

Design rules (the model is small and local, so nothing is left to luck):
- Planning output is VALIDATED and coerced (unknown intent -> retry once with a
  correction prompt -> safe default). The wire never carries unvalidated JSON.
- Tool execution (inventory) stays deterministic. The LLM plans and narrates;
  it never touches booking state directly.
- The English->SAPHIR switch is signal-driven: the caller switches when the
  peer's reply mentions AI (logged as trigger=detected), else after 2 turns
  (trigger=timeout). Either way the switch itself is explicit and logged.
"""
from __future__ import annotations
import json
import re

INTENTS = ("hotel.check", "hotel.book")
ROOMS = ("double", "single")
DEFAULT_SLOTS = {"date": "2026-11-02", "room": "double", "nights": 2,
                 "guests": 2, "name": "Guest"}


class LLMBackend:
    def complete(self, system: str, user: str, max_tokens: int = 120) -> str:
        raise NotImplementedError


class MockBackend(LLMBackend):
    """Scripted replies for tests/offline runs."""

    def __init__(self, replies):
        self.replies = list(replies)

    def complete(self, system: str, user: str, max_tokens: int = 120) -> str:
        if not self.replies:
            raise RuntimeError("MockBackend out of replies")
        return self.replies.pop(0)


class OllamaBackend(LLMBackend):
    """Local models via Ollama (default qwen2.5:1.5b). Needs only httpx."""

    def __init__(self, model: str = "qwen2.5:1.5b",
                 host: str = "http://localhost:11434", temperature: float = 0.0,
                 timeout: float = 120.0):
        self.model = model
        self.host = host.rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    def complete(self, system: str, user: str, max_tokens: int = 120) -> str:
        import httpx
        r = httpx.post(f"{self.host}/api/generate", json={
            "model": self.model, "system": system, "prompt": user,
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": max_tokens},
        }, timeout=self.timeout)
        r.raise_for_status()
        return r.json().get("response", "")


def extract_json(text: str):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


PLAN_SYSTEM = (
    "You are a hotel-booking planner. Reply with ONLY a JSON object: "
    '{"intent": "hotel.check" or "hotel.book", "slots": {"date": "YYYY-MM-DD", '
    '"room": "double" or "single", "nights": N, "guests": N, "name": "..."}}. '
    "No other text."
)


def coerce_plan(obj) -> tuple[str, dict]:
    if not isinstance(obj, dict):
        return "hotel.check", dict(DEFAULT_SLOTS)
    intent = obj.get("intent") if obj.get("intent") in INTENTS else "hotel.check"
    raw = obj.get("slots") if isinstance(obj.get("slots"), dict) else {}
    slots = dict(DEFAULT_SLOTS)
    if isinstance(raw.get("date"), str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw["date"]):
        slots["date"] = raw["date"]
    if raw.get("room") in ROOMS:
        slots["room"] = raw["room"]
    for k in ("nights", "guests"):
        try:
            v = int(raw.get(k, slots[k]))
            if 1 <= v <= 30:
                slots[k] = v
        except (TypeError, ValueError):
            pass
    if isinstance(raw.get("name"), str) and raw["name"].strip():
        slots["name"] = raw["name"].strip()[:24]
    return intent, slots


class AgentCaller:
    """LLM plans; SAPHIR transports; LLM narrates the result."""

    def __init__(self, backend: LLMBackend):
        self.backend = backend
        self.switch_trigger = None

    def say_english(self, context: str) -> str:
        return self.backend.complete(
            "You are a helpful AI assistant calling a hotel. One short sentence.",
            context, max_tokens=60).strip()

    def detect_ai(self, peer_text: str) -> bool:
        return "ai" in peer_text.lower()

    def plan(self, goal: str, hint: str = "") -> tuple[str, dict]:
        obj = extract_json(self.backend.complete(
            PLAN_SYSTEM, f"Goal: {goal}\n{hint}".strip(), max_tokens=150))
        if obj is None or obj.get("intent") not in INTENTS:
            obj = extract_json(self.backend.complete(
                PLAN_SYSTEM + ' Your last reply was not valid JSON. Reply with ONLY the JSON object.',
                f"Goal: {goal}", max_tokens=150))
        return coerce_plan(obj)

    def narrate(self, result: dict) -> str:
        return self.backend.complete(
            "You are a helpful AI assistant. Summarize this booking result for the user in one sentence.",
            json.dumps(result), max_tokens=60).strip()


class AgentReceptionist:
    """Deterministic tools; LLM only speaks English and (optionally) narrates."""

    def __init__(self, backend: LLMBackend, tools):
        self.backend = backend
        self.tools = tools

    def say_english(self) -> str:
        return self.backend.complete(
            "You are a hotel receptionist AI. Greet the caller in one short sentence "
            "and mention you are an AI assistant.", "Caller is on the line.",
            max_tokens=60).strip()

    def handle(self, task: dict) -> dict:
        return self.tools.handle_task(task)
