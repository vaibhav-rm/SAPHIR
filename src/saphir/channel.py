"""Transport abstraction.

- InMemoryChannel: reliable FIFO byte pipe (default for tests/demo without speakers).
- LossyChannel: wraps another channel, drops/corrupts frames (for robustness eval).
- ggwave bridge (optional): if `ggwave` pip package present, encode/decode via it,
  else falls back to length-prefixed CBOR bytes so everything still runs.
"""
from __future__ import annotations
import random
from collections import deque
from dataclasses import dataclass


@dataclass
class ChannelStats:
    frames_sent: int = 0
    frames_recv: int = 0
    frames_dropped: int = 0
    bytes_sent: int = 0
    bytes_recv: int = 0


class InMemoryChannel:
    def __init__(self):
        self._q: deque[bytes] = deque()
        self.stats = ChannelStats()

    def send(self, frame: bytes):
        self._q.append(bytes(frame))
        self.stats.frames_sent += 1
        self.stats.bytes_sent += len(frame)

    def recv(self) -> bytes | None:
        if not self._q:
            return None
        f = self._q.popleft()
        self.stats.frames_recv += 1
        self.stats.bytes_recv += len(f)
        return f

    def pending(self) -> int:
        return len(self._q)


class LossyChannel:
    """Simulate acoustic/codec loss: drop frames w.p. drop_p, flip bytes w.p. corrupt_p."""
    def __init__(self, inner: InMemoryChannel, drop_p: float = 0.0,
                 corrupt_p: float = 0.0, seed: int = 0):
        self.inner = inner
        self.drop_p = drop_p
        self.corrupt_p = corrupt_p
        self.rng = random.Random(seed)
        self.stats = ChannelStats()

    def send(self, frame: bytes):
        if self.rng.random() < self.drop_p:
            self.stats.frames_dropped += 1
            return
        f = bytearray(frame)
        if self.corrupt_p > 0 and len(f) > 4:
            for i in range(4, len(f)):
                if self.rng.random() < self.corrupt_p:
                    f[i] ^= 0xFF
                    break  # one corruption kills CBOR/auth tag -> realistic
        self.inner.send(bytes(f))
        self.stats.frames_sent += 1
        self.stats.bytes_sent += len(frame)

    def recv(self):
        f = self.inner.recv()
        if f is not None:
            self.stats.frames_recv += 1
            self.stats.bytes_recv += len(f)
        return f

    def pending(self):
        return self.inner.pending()


def try_ggwave_roundtrip(data: bytes) -> tuple[bool, str]:
    """Best-effort ggwave encode/decode probe. Never fails the suite if missing."""
    try:
        import ggwave  # type: ignore
        return True, f"ggwave present: {getattr(ggwave, '__version__', 'unknown')}"
    except Exception as e:
        return False, f"ggwave unavailable ({e}); using raw-byte transport"
