"""High-level pairing API: one call to ESTABLISHED, one call per task.

Replaces the hand-rolled handshake drivers previously copy-pasted across
evals. Knows both sessions, so it passes peer-DID hints automatically
(resumption works with zero extra caller code) and counts wire bytes.
"""
from __future__ import annotations

from .channel import InMemoryChannel, LossyChannel
from .protocol import MsgType, decode_envelope, encode_envelope


class LinkError(Exception):
    pass


class LocalLink:
    def __init__(self, a, b, drop_p: float = 0.0, corrupt_p: float = 0.0,
                 seed: int = 0, audit=None):
        self.a = a
        self.b = b
        if drop_p or corrupt_p:
            self.ab = LossyChannel(InMemoryChannel(), drop_p, corrupt_p, seed=seed)
            self.ba = LossyChannel(InMemoryChannel(), drop_p, corrupt_p, seed=seed + 1)
        else:
            self.ab = InMemoryChannel()
            self.ba = InMemoryChannel()
        self.bytes = 0
        self.audit = audit

    def _log(self, direction, env, nbytes):
        self.bytes += nbytes
        if self.audit is not None:
            self.audit.record(direction, env.type, env.sender, env.seq,
                              nbytes, f"{env.type} frame")

    def _send(self, env, ch, direction):
        raw = encode_envelope(env)
        self._log(direction, env, len(raw))
        ch.send(raw)

    def _recv(self, ch):
        raw = ch.recv()
        if raw is None:
            raise LinkError("frame lost (no retransmission in LocalLink)")
        env, _ = decode_envelope(raw)
        return env

    def handshake(self) -> int:
        """Run HELLO..KEY2 (or abbreviated resumption). Returns wire bytes."""
        before = self.bytes
        self._send(self.a.hello(peer_did=self.b.did), self.ab, "A->B")
        w = self.b.handle_hello(self._recv(self.ab))
        self._send(w, self.ba, "B->A")
        k1 = self.a.handle_welcome(self._recv(self.ba))
        if k1 is None:
            return self.bytes - before  # resumed: no KEY frames
        self._send(k1, self.ab, "A->B")
        k2 = self.b.handle_key1(self._recv(self.ab))
        self._send(k2, self.ba, "B->A")
        self.a.handle_key2(self._recv(self.ba))
        return self.bytes - before

    def task(self, intent: str, slots: dict, handler,
             ontology: str = "saphir-hotel-v1") -> dict:
        """One encrypted TASK/RESULT roundtrip; handler(task_dict) -> result_dict."""
        self._send(self.a.seal_task(intent, slots, ontology), self.ab, "A->B")
        t = self.b.open_task(self._recv(self.ab))
        self._send(self.b.seal_result(handler(t)), self.ba, "B->A")
        return self.a.open_result(self._recv(self.ba))
