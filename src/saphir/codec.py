"""Compact task encoding for the acoustic channel.

Same semantics as full-form tasks, short wire keys for the hotel ontology.
Wire form: {"i": intent, "s": {short slots}, "o": onto, "ts": float}
Legacy full-form {"intent","slots","ontology","ts"} still decodes (forward compat).
"""
from __future__ import annotations
import time

INTENT_SHORT = {"hotel.check": "hc", "hotel.book": "hb"}
INTENT_FULL = {v: k for k, v in INTENT_SHORT.items()}
SLOT_SHORT = {"date": "d", "room": "r", "nights": "n", "guests": "g", "name": "nm"}
SLOT_FULL = {v: k for k, v in SLOT_SHORT.items()}
ONTO_SHORT = {"saphir-hotel-v1": "sh1"}
ONTO_FULL = {v: k for k, v in ONTO_SHORT.items()}


def compact_task(intent: str, slots: dict, ontology: str = "saphir-hotel-v1") -> dict:
    cs = {}
    for k, v in slots.items():
        cs[SLOT_SHORT.get(k, k)] = v
    return {"i": INTENT_SHORT.get(intent, intent), "s": cs,
            "o": ONTO_SHORT.get(ontology, ontology), "ts": time.time()}


def expand_task(d: dict) -> dict:
    if "i" not in d:
        return d  # legacy full-form task or RESULT payload: pass through untouched
    slots = {SLOT_FULL.get(k, k): v for k, v in d.get("s", {}).items()}
    return {"intent": INTENT_FULL.get(d.get("i"), d.get("i")), "slots": slots,
            "ontology": ONTO_FULL.get(d.get("o"), d.get("o")), "ts": d.get("ts", 0.0)}
