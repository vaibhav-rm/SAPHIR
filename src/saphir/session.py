"""SAPHIR pairing state machine: HELLO -> WELCOME -> KEY1 -> KEY2 -> TASK* -> BYE.

Each side owns a SaphirSession. Frames are exchanged over a pair of Channels
(a_to_b, b_to_a) or a single shared InMemoryChannel in tests.
"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass, field
from enum import Enum

import cbor2

from .protocol import Envelope, MsgType, MAX_MSG_BYTES
from .crypto import EphemeralKeypair, SessionKeys, derive_session_keys


class SessionState(str, Enum):
    IDLE = "IDLE"
    HELLO_SENT = "HELLO_SENT"
    KEY_SENT = "KEY_SENT"
    ESTABLISHED = "ESTABLISHED"
    CLOSED = "CLOSED"


class HandshakeError(Exception):
    pass


@dataclass
class PeerInfo:
    agent_id: str = ""
    did: str = ""
    codecs: list = field(default_factory=list)


def _fresh_did(agent_id: str) -> str:
    return f"did:key:z{os.urandom(4).hex()}"


class SaphirSession:
    def __init__(self, agent_id: str, did: str | None = None,
                 offers=(), need: str | None = None):
        from .caps import offered_bitmask, BloomFilter
        self.agent_id = agent_id
        self.did = did or _fresh_did(agent_id)
        self.offers = tuple(offers)
        self.need = need
        self.have_mask = offered_bitmask(self.offers)
        self.bloom = BloomFilter()
        for it in self.offers:
            self.bloom.add(it)
        self.verdict = None      # caller's view of responder's WELCOME verdict
        self.peer_need = None    # responder's view of caller's need
        self.state = SessionState.IDLE
        self.seq = 0
        self.peer = PeerInfo()
        self._kp = EphemeralKeypair.generate()
        self._peer_pub: bytes | None = None
        self.keys: SessionKeys | None = None
        self._seen_seq: set[int] = set()
        self.selected_codec = "saphir-cbor-v1"

    # ---- handshake initiators ----
    def hello(self) -> Envelope:
        from .protocol import build_hello
        from .caps import INTENT_IDS
        env = build_hello(self.agent_id, self.did, self.seq)
        if self.need:  # int id if registered, else the raw string (open vocab)
            env.payload["need"] = INTENT_IDS.get(self.need, self.need)
        if self.have_mask:  # omit empties: absence == none offered
            env.payload["have"] = self.have_mask
            if any(self.bloom.bits):
                env.payload["bloom"] = self.bloom.wire()
        self.seq += 1
        self.state = SessionState.HELLO_SENT
        return env

    def handle_hello(self, env: Envelope) -> Envelope:
        from .protocol import normalize_codecs
        from .caps import INTENT_NAMES, match
        p = env.payload
        if not isinstance(p, dict) or "did" not in p:
            raise HandshakeError("malformed HELLO")
        self.peer = PeerInfo(agent_id=p.get("agent_id", env.sender), did=p["did"],
                             codecs=normalize_codecs(p.get("codec", p.get("codecs", []))))
        raw_need = p.get("need", 0)
        self.peer_need = INTENT_NAMES.get(raw_need, raw_need) if raw_need else None
        verdict = match(self.peer_need, self.have_mask, self.bloom) if self.peer_need else "exact"
        # answer WELCOME (echo our did + selected codec + capability verdict)
        self.state = SessionState.HELLO_SENT
        code = {"exact": 2, "maybe": 1, "no": 0}[verdict]
        return Envelope(type=MsgType.WELCOME, seq=self.seq, sender=self.agent_id,
                        nonce=os.urandom(16),
                        payload={"did": self.did, "sel": 1, "modes": 3,
                                 "for": p.get("need", 0), "match": code,
                                 "ts": int(time.time())})

    def handle_welcome(self, env: Envelope) -> Envelope:
        from .protocol import normalize_selected
        p = env.payload
        self.peer = Peerinfo_fix(p)
        if not self.peer.agent_id:
            self.peer.agent_id = env.sender
        self.selected_codec = normalize_selected(p.get("sel", p.get("selected")),
                                                 self.selected_codec)
        self.verdict = {2: "exact", 1: "maybe", 0: "no"}.get(p.get("match", 2), "exact")
        key1 = Envelope(type=MsgType.KEY1, seq=self.seq, sender=self.agent_id,
                        nonce=os.urandom(16), payload={"pub": self._kp.pub_bytes})
        self.seq += 1
        self.state = SessionState.KEY_SENT
        return key1

    def handle_key1(self, env: Envelope) -> Envelope:
        self._peer_pub = bytes(env.payload["pub"])
        self.keys = derive_session_keys(self._kp, self._peer_pub)
        self.state = SessionState.ESTABLISHED
        key2 = Envelope(type=MsgType.KEY2, seq=self.seq, sender=self.agent_id,
                        nonce=os.urandom(16), payload={"pub": self._kp.pub_bytes})
        self.seq += 1
        return key2

    def handle_key2(self, env: Envelope):
        self._peer_pub = bytes(env.payload["pub"])
        self.keys = derive_session_keys(self._kp, self._peer_pub)
        self.state = SessionState.ESTABLISHED
        return None

    # ---- secure messaging ----
    def seal_task(self, intent: str, slots: dict, ontology: str = "saphir-hotel-v1") -> Envelope:
        if self.state != SessionState.ESTABLISHED or self.keys is None:
            raise HandshakeError("session not established")
        from .codec import compact_task
        pt = cbor2.dumps(compact_task(intent, slots, ontology))
        nonce, ct = self.keys.seal(pt, aad=self.agent_id.encode())
        env = Envelope(type=MsgType.TASK, seq=self.seq, sender=self.agent_id,
                       nonce=nonce, payload=ct)
        self.seq += 1
        return env

    def open_task(self, env: Envelope) -> dict:
        if self.state != SessionState.ESTABLISHED or self.keys is None:
            raise HandshakeError("session not established")
        if env.seq in self._seen_seq:
            raise HandshakeError(f"replay: seq {env.seq} reused")
        self._seen_seq.add(env.seq)
        pt = self.keys.open(bytes(env.nonce), bytes(env.payload), aad=env.sender.encode())
        from .codec import expand_task
        return expand_task(cbor2.loads(pt))

    def seal_result(self, result: dict) -> Envelope:
        if self.state != SessionState.ESTABLISHED or self.keys is None:
            raise HandshakeError("session not established")
        pt = cbor2.dumps(result)
        nonce, ct = self.keys.seal(pt, aad=self.agent_id.encode())
        env = Envelope(type=MsgType.RESULT, seq=self.seq, sender=self.agent_id,
                       nonce=nonce, payload=ct)
        self.seq += 1
        return env

    def open_result(self, env: Envelope) -> dict:
        return self.open_task(env)  # same AEAD path

    def refuse(self, intent: str) -> Envelope:
        """Polite decline for a TASK nobody offered: plaintext ERROR frame."""
        env = Envelope(type=MsgType.ERROR, seq=self.seq, sender=self.agent_id,
                       nonce=os.urandom(12),
                       payload={"code": "no-capability", "want": intent})
        self.seq += 1
        return env


def Peerinfo_fix(p: dict) -> PeerInfo:
    from .protocol import normalize_codecs
    return PeerInfo(agent_id=p.get("agent_id", ""), did=p.get("did", ""),
                    codecs=normalize_codecs(p.get("codec", p.get("codecs", []))))
