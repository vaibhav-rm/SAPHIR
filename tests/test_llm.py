import sys
sys.path.insert(0, "src")
from saphir import (SaphirSession, LocalLink, ReceptionistAgent,
                    AgentCaller, AgentReceptionist, MockBackend,
                    coerce_plan, extract_json)

SCRIPT = [
    "Hi, I'd like to book a double room for November 2nd.",
    "Welcome! I am an AI receptionist, how can I help?",
    '{"intent": "hotel.check", "slots": {"date": "2026-11-02", "room": "double", "nights": 2}}',
    '{"intent": "hotel.book", "slots": {"date": "2026-11-02", "room": "double", "nights": 2, "guests": 2, "name": "Vaibhav"}}',
    "Booked! Confirmation HB-2026-1142.",
]


def test_coerce_plan_hardens_garbage():
    intent, slots = coerce_plan({"intent": "nuke.launch", "slots": {"room": "penthouse", "nights": -5}})
    assert intent == "hotel.check" and slots["room"] == "double" and slots["nights"] == 2
    intent, slots = coerce_plan("not json at all")
    assert intent == "hotel.check"
    assert extract_json("no braces here") is None


def test_ai_dialogue_over_saphir():
    sys.path.insert(0, "demo")
    from ai_dialogue import run
    out = run(MockBackend(list(SCRIPT)), verbose=False)
    text = "\n".join(out)
    assert "[switch: detected]" in text
    assert "[paired]" in text and "verdict=exact" in text
    assert "'ok': True" in text or '"ok": True' in text or "ok" in text
    assert "confirmation" in text.lower() or "HB-2026" in text


def test_switch_timeout_path():
    backend = MockBackend([
        "Hello, how can I help you today?",  # no AI mention -> timeout path
        "Are you an AI agent like me?",
        '{"intent": "hotel.check", "slots": {}}',
        '{"intent": "hotel.book", "slots": {}}',
        "Done.",
    ])
    caller = AgentCaller(backend)
    line = caller.say_english("hi")
    assert caller.detect_ai(line) is False
