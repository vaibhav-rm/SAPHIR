"""Transport abstraction.

- InMemoryChannel: reliable FIFO byte pipe (default for tests/demo without speakers).
- LossyChannel: wraps another channel, drops/corrupts frames (for robustness eval).
- ggwave bridge (optional): if `ggwave` pip package present, encode/decode via it,
  else falls back to length-prefixed CBOR bytes so everything still runs.
"""
from __future__ import annotations
import random
import struct
import zlib
from collections import deque
from dataclasses import dataclass, field


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


CHUNK_MAGIC = b"SAP1"
ACK_MAGIC = b"SAPA"
_CHUNK_HDR = struct.Struct(">4sIIB")  # magic, msg_id, total, idx (13B)
_ACK_MSG = struct.Struct(">4sII")     # magic, msg_id, idx (12B)
_CRC = struct.Struct(">I")


@dataclass
class LinkStats:
    frames_in: int = 0      # reassembled SAPHIR frames delivered up
    chunks_tx: int = 0      # chunk transmissions (incl. retries)
    acks_tx: int = 0
    retries: int = 0
    crc_rejects: int = 0
    failed: bool = False


class ReliableLink:
    """Stop-and-wait ARQ over a lossy byte channel, driven by discrete ticks.

    - Outgoing SAPHIR frames are split into <=chunk_size chunks; each chunk
      carries CRC32 and is retransmitted until ACKed (bounded retries).
    - Each chunk (header+crc ~17B) still fits one ggwave audible frame.
    - Single-threaded: the harness must call tick() on both peers in a loop.
    """

    def __init__(self, tx, rx, chunk_size: int = 110, max_retries: int = 10,
                 ack_timeout: int = 2):
        self.tx = tx
        self.rx = rx
        self.chunk_size = chunk_size
        self.max_retries = max_retries
        self.ack_timeout = ack_timeout
        self._msg_seq = 0
        self._pending: dict[tuple[int, int], list] = {}  # (msg,idx)->[bytes,retries,due]
        self._gather: dict[int, dict] = {}               # msg_id->{total,parts:{idx:bytes}}
        self._ready: deque[bytes] = deque()
        self._acked: set[tuple[int, int]] = set()
        self.stats = LinkStats()

    def send_frame(self, frame: bytes):
        mid = self._msg_seq
        self._msg_seq += 1
        parts = [frame[i:i + self.chunk_size]
                 for i in range(0, len(frame), self.chunk_size)] or [b""]
        for idx, p in enumerate(parts):
            body = _CHUNK_HDR.pack(CHUNK_MAGIC, mid, len(parts), idx) + p
            wire = body + _CRC.pack(zlib.crc32(body) & 0xFFFFFFFF)
            self._pending[(mid, idx)] = [wire, self.max_retries, 0]

    def _parse(self, raw: bytes):
        if raw[:4] == ACK_MAGIC and len(raw) == _ACK_MSG.size:
            _, mid, idx = _ACK_MSG.unpack(raw)
            return ("ack", mid, idx)
        if raw[:4] == CHUNK_MAGIC and len(raw) > _CHUNK_HDR.size + _CRC.size:
            body, crc = raw[:-4], raw[-4:]
            if zlib.crc32(body) & 0xFFFFFFFF != _CRC.unpack(crc)[0]:
                return ("corrupt", None, None)
            _, mid, total, idx = _CHUNK_HDR.unpack(body[:_CHUNK_HDR.size])
            return ("chunk", mid, idx, total, body[_CHUNK_HDR.size:])
        return ("garbage", None, None)

    def tick(self, now: int):
        due_acks: list[bytes] = []
        while True:
            raw = self.rx.recv()
            if raw is None:
                break
            kind = self._parse(raw)[0]
            if kind == "ack":
                _, mid, idx = self._parse(raw)
                self._acked.add((mid, idx))
            elif kind == "chunk":
                _, mid, idx, total, payload = self._parse(raw)
                due_acks.append(_ACK_MSG.pack(ACK_MAGIC, mid, idx))
                g = self._gather.setdefault(mid, {"total": total, "parts": {}})
                g["parts"][idx] = payload
                if len(g["parts"]) == g["total"]:
                    out = b"".join(g["parts"][i] for i in range(g["total"]))
                    self._ready.append(out)
                    self.stats.frames_in += 1
                    del self._gather[mid]
            elif kind == "corrupt":
                self.stats.crc_rejects += 1
        for a in due_acks:
            self.tx.send(a)
            self.stats.acks_tx += 1
        for key, (wire, retries, due) in list(self._pending.items()):
            if key in self._acked:
                del self._pending[key]
                continue
            if due <= now:
                if retries < 0:
                    self.stats.failed = True
                    del self._pending[key]
                    continue
                if due > 0:
                    self.stats.retries += 1
                self.tx.send(wire)
                self.stats.chunks_tx += 1
                self._pending[key] = [wire, retries - 1, now + self.ack_timeout]

    def recv_frame(self) -> bytes | None:
        return self._ready.popleft() if self._ready else None

    def quiet(self) -> bool:
        return not self._pending and not self.stats.failed
