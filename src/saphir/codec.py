"""Compact task encoding for the acoustic channel.

Same semantics as full-form tasks, short wire keys for the hotel ontology.
Wire form: {"i": intent, "s": {short slots}, "o": onto, "ts": float}
Legacy full-form {"intent","slots","ontology","ts"} still decodes (forward compat).
"""
from __future__ import annotations
import time

INTENT_SHORT = {"hotel.check": "hc", "hotel.book": "hb",
                "taxi.request": "tr", "taxi.book": "tb"}
INTENT_FULL = {v: k for k, v in INTENT_SHORT.items()}
SLOT_SHORT = {"date": "d", "room": "r", "nights": "n", "guests": "g", "name": "nm",
              "from": "f", "to": "t", "seats": "s", "time": "tm"}
SLOT_FULL = {v: k for k, v in SLOT_SHORT.items()}
ONTO_SHORT = {"saphir-hotel-v1": "sh1", "saphir-taxi-v1": "st1"}
ONTO_FULL = {v: k for k, v in ONTO_SHORT.items()}
DEFAULT_ONTO = "saphir-hotel-v1"
# Value shorts: room types, locations, YYMMDD dates (expand is backward compatible).
# Demo-scale dictionary coding; schema-driven dictionaries negotiated in HELLO
# are the scalable version (future work).
VALUE_SHORT = {"double": "dbl", "single": "sng",
               "RVCE": "rv", "Majestic": "maj", "Airport": "ap"}
VALUE_FULL = {v: k for k, v in VALUE_SHORT.items()}


def _compact_value(slot: str, v):
    if isinstance(v, str) and v in VALUE_SHORT:
        return VALUE_SHORT[v]
    if slot == "date" and isinstance(v, str) and len(v) == 10 and v[4] == "-" and v[7] == "-":
        return v[2:4] + v[5:7] + v[8:10]  # 2026-11-02 -> 261102
    return v


def _expand_value(slot: str, v):
    if isinstance(v, str) and v in VALUE_FULL:
        return VALUE_FULL[v]
    if slot == "date" and isinstance(v, str) and len(v) == 6 and v.isdigit():
        return "20" + v[0:2] + "-" + v[2:4] + "-" + v[4:6]
    return v


def compact_task(intent: str, slots: dict, ontology: str = DEFAULT_ONTO) -> dict:
    cs = {}
    for k, v in slots.items():
        cs[SLOT_SHORT.get(k, k)] = _compact_value(k, v)
    d = {"i": INTENT_SHORT.get(intent, intent), "s": cs, "ts": int(time.time())}
    if ontology != DEFAULT_ONTO:
        d["o"] = ONTO_SHORT.get(ontology, ontology)  # default ontology omitted
    return d


def expand_task(d: dict) -> dict:
    if "i" not in d:
        return d  # legacy full-form task or RESULT payload: pass through untouched
    slots = {SLOT_FULL.get(k, k): _expand_value(SLOT_FULL.get(k, k), v)
             for k, v in d.get("s", {}).items()}
    onto = d.get("o", ONTO_SHORT[DEFAULT_ONTO])
    return {"intent": INTENT_FULL.get(d.get("i"), d.get("i")), "slots": slots,
            "ontology": ONTO_FULL.get(onto, onto), "ts": d.get("ts", 0.0)}
