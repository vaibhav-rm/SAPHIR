"""Two REAL AI agents: English first, then SAPHIR. Usage:

  PYTHONPATH=src python demo/ai_dialogue.py [--backend ollama|mock] [--goal "..."]
"""
import sys
import time
sys.path.insert(0, "src")
from saphir import (SaphirSession, LocalLink, ReceptionistAgent,
                    AgentCaller, AgentReceptionist, MockBackend, OllamaBackend)

GOAL = "book a double room for 2026-11-02, 2 nights, 2 guests, name Vaibhav"


def run(backend, goal=GOAL, verbose=True):
    out = []
    log = lambda s: (print(s, flush=True) if verbose else None, out.append(s))[1]

    caller_ai = AgentCaller(backend)
    recep_ai = AgentReceptionist(backend, ReceptionistAgent())

    # --- Act 1: English (both sides LLM-generated) ---
    t0 = time.time()
    c1 = caller_ai.say_english("Call the hotel. Ask to book a double room for Nov 2, 2 nights.")
    log(f"[caller EN] {c1}")
    r1 = recep_ai.say_english()
    log(f"[recep  EN] {r1}")
    if caller_ai.detect_ai(r1):
        caller_ai.switch_trigger = "detected"
    else:
        c2 = caller_ai.say_english("Ask plainly: are you an AI agent like me?")
        log(f"[caller EN] {c2}")
        caller_ai.switch_trigger = "timeout"
    log(f"[switch: {caller_ai.switch_trigger}] let's speak SAPHIR")

    # --- Act 2: handshake + LLM-planned structured tasks ---
    a = SaphirSession("caller", need="hotel.book")
    b = SaphirSession("receptionist", offers=["hotel.check", "hotel.book"])
    link = LocalLink(a, b)
    nbytes = link.handshake()
    log(f"[paired] {nbytes}B, verdict={a.verdict}")

    intent, slots = caller_ai.plan(goal, hint="This step: reply with hotel.check intent only.")
    if intent != "hotel.check":
        intent, slots = "hotel.check", {**slots, "name": "Vaibhav"}
    log(f"[planned] {intent} {slots}")
    res1 = link.task(intent, slots, recep_ai.handle)
    log(f"[result ] {res1}")

    intent2, slots2 = caller_ai.plan(
        goal + f" Availability: {res1}. Now book it.",
        hint="This step: reply with hotel.book intent only.")
    if intent2 != "hotel.book":
        intent2 = "hotel.book"  # script guard: second step must book
    log(f"[planned] {intent2} {slots2}")
    res2 = link.task(intent2, slots2, recep_ai.handle)
    log(f"[result ] {res2}")

    # --- Act 3: LLM narrates the outcome ---
    log(f"[caller EN] {caller_ai.narrate(res2)}")
    log(f"done in {time.time() - t0:.0f}s over {link.bytes}B on the wire")
    return out


if __name__ == "__main__":
    backend_name = sys.argv[sys.argv.index("--backend") + 1] if "--backend" in sys.argv else "ollama"
    goal = sys.argv[sys.argv.index("--goal") + 1] if "--goal" in sys.argv else GOAL
    if backend_name == "mock":
        backend = MockBackend([
            "Hi, I'd like to book a double room for November 2nd.",
            "Welcome! I am an AI receptionist, how can I help?",
            '{"intent": "hotel.check", "slots": {"date": "2026-11-02", "room": "double", "nights": 2}}',
            '{"intent": "hotel.book", "slots": {"date": "2026-11-02", "room": "double", "nights": 2, "guests": 2, "name": "Vaibhav"}}',
            "Booked! Confirmation HB-2026-1142, total $240.",
        ])
    else:
        try:
            import httpx
            httpx.get("http://localhost:11434/api/tags", timeout=5).raise_for_status()
        except Exception:
            print("ollama not reachable; falling back to --backend mock")
            sys.exit(2)
        backend = OllamaBackend()
    run(backend, goal)
