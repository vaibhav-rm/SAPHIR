"""Toy hotel-booking agents: rule-based, no LLM API needed for baseline.

Caller wants {checkin, nights, room, guests}; Receptionist has inventory.
Dialogue runs EITHER as English strings (Act 1: wasteful speech loop) OR as
SAPHIR TASK/RESULT dicts (Act 2: structured).
"""
from __future__ import annotations
from dataclasses import dataclass, field


INVENTORY = {
    ("2026-11-02", "double"): {"price": 120, "left": 3},
    ("2026-11-02", "single"): {"price": 80, "left": 5},
}

ENGLISH_SCRIPT = [
    ("caller", "Hi, I'd like to book a double room for November 2nd, 2 nights, 2 guests."),
    ("receptionist", "Let me check... yes, double rooms available at $120 per night."),
    ("caller", "Great, please book it under Vaibhav."),
    ("receptionist", "Done! Confirmation HB-2026-1142, total $240."),
]

STRUCTURED_TASKS = [
    {"intent": "hotel.check", "slots": {"date": "2026-11-02", "room": "double", "nights": 2}},
    {"intent": "hotel.book", "slots": {"date": "2026-11-02", "room": "double", "nights": 2,
                                       "guests": 2, "name": "Vaibhav"}},
]


@dataclass
class CallerAgent:
    name: str = "caller"

    def english_turns(self):
        return [t for who, t in ENGLISH_SCRIPT if who == "caller"]


@dataclass
class ReceptionistAgent:
    name: str = "receptionist"
    inventory: dict = field(default_factory=lambda: {k: dict(v) for k, v in INVENTORY.items()})

    def handle_task(self, task: dict) -> dict:
        intent, slots = task.get("intent"), task.get("slots", {})
        if intent == "hotel.check":
            key = (slots.get("date"), slots.get("room"))
            avail = self.inventory.get(key)
            if avail and avail["left"] > 0:
                return {"ok": True, "price": avail["price"], "left": avail["left"],
                        "quote": avail["price"] * slots.get("nights", 1)}
            return {"ok": False, "error": "sold out"}
        if intent == "hotel.book":
            key = (slots.get("date"), slots.get("room"))
            avail = self.inventory.get(key)
            if avail and avail["left"] > 0:
                avail["left"] -= 1
                total = avail["price"] * slots.get("nights", 1)
                return {"ok": True, "confirmation": "HB-2026-1142", "total": total}
            return {"ok": False, "error": "sold out"}
        return {"ok": False, "error": f"unknown intent {intent}"}


def run_booking_dialogue():
    """Returns (english_chars, structured_slots_chars) for savings estimate."""
    eng = sum(len(t) for _, t in ENGLISH_SCRIPT)
    import json
    st = sum(len(json.dumps(t)) for t in STRUCTURED_TASKS)
    return eng, st


# ---- Second domain: taxi dispatch (proves the ontology/encoding generalizes) ----
TAXI_FLEET = {
    ("RVCE", "Majestic"): {"fare": 250, "eta_min": 15, "cars": 4},
    ("RVCE", "Airport"): {"fare": 900, "eta_min": 40, "cars": 2},
}

TAXI_TASKS = [
    {"intent": "taxi.request", "slots": {"from": "RVCE", "to": "Majestic",
                                         "seats": 2, "time": "18:00"},
     "ontology": "saphir-taxi-v1"},
    {"intent": "taxi.book", "slots": {"from": "RVCE", "to": "Majestic",
                                      "seats": 2, "time": "18:00", "name": "Vaibhav"},
     "ontology": "saphir-taxi-v1"},
]


@dataclass
class TaxiDispatch:
    name: str = "dispatch"
    fleet: dict = field(default_factory=lambda: {k: dict(v) for k, v in TAXI_FLEET.items()})

    def handle_task(self, task: dict) -> dict:
        intent, slots = task.get("intent"), task.get("slots", {})
        key = (slots.get("from"), slots.get("to"))
        car = self.fleet.get(key)
        if intent == "taxi.request":
            if car and car["cars"] > 0:
                return {"ok": True, "fare": car["fare"], "eta_min": car["eta_min"]}
            return {"ok": False, "error": "no cars"}
        if intent == "taxi.book":
            if car and car["cars"] > 0:
                car["cars"] -= 1
                return {"ok": True, "confirmation": "TX-2026-0713",
                        "fare": car["fare"], "eta_min": car["eta_min"]}
            return {"ok": False, "error": "no cars"}
        return {"ok": False, "error": f"unknown intent {intent}"}
