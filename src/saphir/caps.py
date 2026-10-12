"""Capability discovery for the acoustic budget.

Two layers, both tens of bytes:
- Closed registry bitmask (exact): known intents from INTENT_IDS, 1 byte.
- Open bloom filter (probabilistic, 10B): arbitrary capability strings.
  A bloom hit only earns a TASK attempt — FPR costs one roundtrip, never a
  wrong execution. A miss means definite absence: decline fast.

HELLO carries {"need": int|None, "have": int bitmask, "bloom": bytes(10)}.
"""
from __future__ import annotations
import hashlib

INTENT_IDS = {"hotel.check": 1, "hotel.book": 2, "taxi.request": 3, "taxi.book": 4}
INTENT_NAMES = {v: k for k, v in INTENT_IDS.items()}

BLOOM_BYTES = 10
BLOOM_BITS = BLOOM_BYTES * 8
BLOOM_K = 3


class BloomFilter:
    def __init__(self, bits: bytes = None):
        self.bits = bytearray(bits) if bits else bytearray(BLOOM_BYTES)

    def _hashes(self, item: str):
        h = hashlib.sha256(item.encode()).digest()
        for i in range(BLOOM_K):
            yield int.from_bytes(h[2 * i:2 * i + 2], "big") % BLOOM_BITS

    def add(self, item: str):
        for b in self._hashes(item):
            self.bits[b // 8] |= 1 << (b % 8)

    def __contains__(self, item: str) -> bool:
        return all(self.bits[b // 8] >> (b % 8) & 1 for b in self._hashes(item))

    def wire(self) -> bytes:
        return bytes(self.bits)

    @classmethod
    def from_wire(cls, raw: bytes) -> "BloomFilter":
        if len(raw) != BLOOM_BYTES:
            raise ValueError(f"bloom must be {BLOOM_BYTES}B, got {len(raw)}")
        return cls(raw)


def offered_bitmask(intents) -> int:
    mask = 0
    for it in intents:
        if it in INTENT_IDS:
            mask |= 1 << INTENT_IDS[it]
    return mask


def match(need: str, have_mask: int, bloom: BloomFilter) -> str:
    """Returns 'exact' | 'maybe' | 'no':
    exact = registry bit set; maybe = bloom hit only (confirm via TASK);
    no = definite absence -> decline fast."""
    if need in INTENT_IDS and (have_mask >> INTENT_IDS[need]) & 1:
        return "exact"
    if need in bloom:
        return "maybe"
    return "no"
