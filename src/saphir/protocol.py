"""SAPHIR message envelope + CBOR codec.

Wire format (transport-agnostic, fits in ggwave frames):
    [4-byte big-endian len][CBOR(envelope)]

Envelope:
    {v: int, type: str, seq: int, sender: str, nonce: bytes, payload: dict|bytes}

TASK/RESULT payloads are ChaCha20Poly1305-encrypted bytes after session keys
are established; HELLO/WELCOME/KEY1/KEY2/ERROR are plaintext for handshake.
"""
from __future__ import annotations
import os
import struct
import time
from dataclasses import dataclass, field
from enum import Enum

import cbor2

PROTOCOL_VERSION = 1
# ggwave audible-normal is ~16-32 bps reliable; a "frame" here maps to 1-2
# ggwave transmissions. MVP cap 200B (measured TASK ~170-185B encrypted).
MAX_MSG_BYTES = 200  # TASK/RESULT must fit; handshake frames are smaller
LEN_PREFIX = struct.Struct(">I")


class MsgType(str, Enum):
    HELLO = "HELLO"
    WELCOME = "WELCOME"
    KEY1 = "KEY1"
    KEY2 = "KEY2"
    TASK = "TASK"
    RESULT = "RESULT"
    ACK = "ACK"
    ERROR = "ERROR"
    BYE = "BYE"


@dataclass
class HelloPayload:
    agent_id: str
    did: str  # e.g. "did:key:z..." ephemeral for this pairing
    codecs: list = field(default_factory=lambda: ["saphir-cbor-v1"])
    modes: list = field(default_factory=lambda: ["audio", "hybrid"])
    nonce: bytes = field(default_factory=lambda: os.urandom(16))
    ts: float = field(default_factory=time.time)


@dataclass
class TaskPayload:
    intent: str  # e.g. "hotel.book"
    slots: dict = field(default_factory=dict)
    ontology: str = "saphir-hotel-v1"
    nonce: bytes = field(default_factory=lambda: os.urandom(12))
    ts: float = field(default_factory=time.time)


@dataclass
class Envelope:
    type: str
    seq: int
    sender: str
    nonce: bytes
    payload: dict | bytes

    def to_dict(self) -> dict:
        return {"v": PROTOCOL_VERSION, "type": self.type, "seq": self.seq,
                "sender": self.sender, "nonce": self.nonce, "payload": self.payload}


def encode_envelope(env: Envelope) -> bytes:
    raw = cbor2.dumps(env.to_dict())
    if len(raw) > MAX_MSG_BYTES and env.type in (MsgType.TASK, MsgType.RESULT):
        raise ValueError(f"encrypted payload too large: {len(raw)} > {MAX_MSG_BYTES}; shrink slots")
    return LEN_PREFIX.pack(len(raw)) + raw


def decode_envelope(buf: bytes) -> tuple[Envelope, bytes]:
    """Decode one frame from front of buf. Returns (envelope, remaining)."""
    if len(buf) < LEN_PREFIX.size:
        raise ValueError("short buffer: need len prefix")
    (n,) = LEN_PREFIX.unpack(buf[:LEN_PREFIX.size])
    if len(buf) < LEN_PREFIX.size + n:
        raise ValueError(f"short buffer: need {n} payload bytes")
    obj = cbor2.loads(buf[LEN_PREFIX.size:LEN_PREFIX.size + n])
    if obj.get("v") != PROTOCOL_VERSION:
        raise ValueError(f"unsupported version {obj.get('v')}")
    env = Envelope(type=obj["type"], seq=int(obj["seq"]), sender=obj["sender"],
                   nonce=obj["nonce"], payload=obj["payload"])
    return env, buf[LEN_PREFIX.size + n:]


def build_hello(agent_id: str, did: str, seq: int = 0) -> Envelope:
    p = HelloPayload(agent_id=agent_id, did=did)
    return Envelope(type=MsgType.HELLO, seq=seq, sender=agent_id,
                    nonce=p.nonce, payload={"agent_id": p.agent_id, "did": p.did,
                                            "codecs": p.codecs, "modes": p.modes,
                                            "nonce": p.nonce, "ts": p.ts})


def build_task(sender: str, seq: int, intent: str, slots: dict,
               ontology: str = "saphir-hotel-v1") -> TaskPayload:
    return TaskPayload(intent=intent, slots=slots, ontology=ontology)
