"""Handshake admission guard: freshness + per-peer rate limiting.

Why this exists: the acoustic handshake is plaintext and cheap to initiate,
so a nearby speaker can flood HELLOs (battery/CPU DoS) or replay a stale
HELLO captured earlier. SAPHIR already rejects forged/replayed TASKs via
AEAD + seq, but HELLO admission had no policy. This module adds the
missing front door:

- freshness: HELLO carries ``ts`` (int seconds, set by ``build_hello``);
  responders reject frames older/newer than ``max_skew_s``.
- rate limit: token-bucket per sender id; excess HELLOs are refused before
  any crypto work, with a plaintext ERROR-let approach left to the caller.

Both are opt-in via ``SaphirSession(max_skew_s=..., guard=...)`` so existing
callers and byte counts are unchanged unless enabled.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field


def hello_age_s(hello_ts: int | float, now: float | None = None) -> float:
    """Signed age: positive = hello from the past, negative = from the future."""
    now = time.time() if now is None else now
    return now - float(hello_ts)


def is_fresh(hello_ts: int | float, max_skew_s: float = 300,
             now: float | None = None) -> bool:
    """True when the HELLO timestamp is within ±max_skew_s of now."""
    return abs(hello_age_s(hello_ts, now)) <= max_skew_s


@dataclass
class HandshakeGuard:
    """Per-sender token bucket for HELLO admission.

    ``max_hellos`` frames per ``window_s`` seconds per sender id.
    ``allow()`` returns True and consumes a token, False when the peer
    must back off. ``refused`` counts total refusals (for metrics).
    """

    max_hellos: int = 5
    window_s: float = 60.0
    _hits: dict = field(default_factory=lambda: defaultdict(list), repr=False)
    refused: int = 0

    def allow(self, sender: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        hits = self._hits[sender]
        cutoff = now - self.window_s
        while hits and hits[0] <= cutoff:
            hits.pop(0)
        if len(hits) >= self.max_hellos:
            self.refused += 1
            return False
        hits.append(now)
        return True

    def reset(self, sender: str | None = None) -> None:
        if sender is None:
            self._hits.clear()
        else:
            self._hits.pop(sender, None)
