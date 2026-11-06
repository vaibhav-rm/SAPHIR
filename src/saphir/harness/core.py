"""SAPHIR harness core: one object that owns a session + transport + audit log.

This is the layer an AI runtime talks to. It hides the handshake shape
(initiator vs responder), auto-pairs before the first task, enforces the
capability allow-list, and records every frame to the human-readable sidecar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..audit import AuditLog
from ..guard import HandshakeGuard
from ..protocol import MsgType, decode_envelope, encode_envelope
from ..resume import TicketStore
from ..session import HandshakeError, SaphirSession, SessionState
from .transport import DEFAULT_TIMEOUT, Transport

INITIATOR = "initiator"
RESPONDER = "responder"
ROLES = (INITIATOR, RESPONDER)


class HarnessError(Exception):
    pass


class HarnessTimeout(HarnessError):
    pass


def _type_name(t) -> str:
    return str(getattr(t, "value", t))


@dataclass
class HarnessConfig:
    agent_id: str
    role: str = INITIATOR
    offers: tuple[str, ...] = ()
    need: str | None = None
    ontology: str = "saphir-hotel-v1"
    handler: Callable[[dict], dict] | None = None
    audit_path: str | None = None
    transport: Transport | None = None
    # Stable DID enables resumption; omit for a fresh ephemeral DID per process.
    did: str | None = None
    resume: bool = True
    max_skew_s: float | None = 300
    guard: HandshakeGuard | None = None
    timeout: float = DEFAULT_TIMEOUT

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {ROLES}, got {self.role!r}")
        if self.transport is None:
            raise ValueError("HarnessConfig requires a transport")


class SaphirHarness:
    """Pair once, then exchange encrypted TASK/RESULT frames."""

    def __init__(self, config: HarnessConfig):
        self.cfg = config
        self.transport = config.transport
        self.audit = AuditLog(config.audit_path) if config.audit_path else None
        self.store = TicketStore() if config.resume else None
        self.bytes_sent = 0
        self.bytes_received = 0
        self._peer_did: str | None = None
        self._session: SaphirSession | None = None
        self._last_in = None
        self._new_session()

    # ---- session plumbing ----
    def _new_session(self):
        self._session = SaphirSession(
            self.cfg.agent_id,
            did=self.cfg.did,
            offers=self.cfg.offers,
            need=self.cfg.need,
            store=self.store,
            max_skew_s=self.cfg.max_skew_s,
            guard=self.cfg.guard,
        )

    @property
    def session(self) -> SaphirSession:
        return self._session

    @property
    def state(self) -> str:
        return self._session.state.value

    @property
    def is_paired(self) -> bool:
        return self._session.state in (SessionState.ESTABLISHED, SessionState.RESUMING)

    # ---- framing ----
    def _record(self, direction: str, env, nbytes: int, decrypted=None):
        if self.audit is None:
            return
        t = _type_name(env.type)
        detail = ""
        if isinstance(decrypted, dict):
            if t == "TASK":
                detail = f" intent={decrypted.get('intent')} slots={decrypted.get('slots')}"
            else:
                detail = f" {decrypted}"
        summary = {
            "HELLO": "pairing request",
            "WELCOME": "pairing accepted",
            "KEY1": "ephemeral key",
            "KEY2": "ephemeral key + session established",
            "TASK": "encrypted task",
            "RESULT": "encrypted result",
            "ERROR": "error frame",
            "BYE": "teardown",
        }.get(t, t)
        self.audit.record(direction, t, env.sender, env.seq, nbytes, summary + detail,
                          decrypted)

    def _send(self, env, decrypted=None):
        raw = encode_envelope(env)
        self.transport.send(raw)
        self.bytes_sent += len(raw)
        self._record("out", env, len(raw), decrypted)

    def _recv(self, timeout: float | None = None):
        raw = self.transport.recv(self.cfg.timeout if timeout is None else timeout)
        if raw is None:
            raise HarnessTimeout("timed out waiting for a frame")
        self.bytes_received += len(raw)
        try:
            env, _ = decode_envelope(raw)
        except Exception as e:  # malformed frame from the wire
            raise HarnessError(f"undecodable frame: {e}") from e
        self._last_in = (env, len(raw))
        return env

    def _record_in(self, decrypted=None):
        if self._last_in is not None:
            env, n = self._last_in
            self._record("in", env, n, decrypted)
            self._last_in = None

    # ---- pairing ----
    def pair(self, timeout: float | None = None) -> dict:
        """Run (or resume) the handshake. Safe to call when already paired."""
        if self.is_paired:
            return self.status()
        if self._session.state == SessionState.CLOSED:
            self._new_session()

        if self.cfg.role == INITIATOR:
            self._send(self._session.hello(peer_did=self._peer_did))
            while True:
                env = self._recv(timeout)
                self._record_in()
                t = _type_name(env.type)
                if t == "WELCOME":
                    key1 = self._session.handle_welcome(env)
                    if key1 is None:  # resumed: no KEY frames
                        break
                    self._send(key1)
                elif t == "KEY2":
                    self._session.handle_key2(env)
                    break
                elif t in ("ERROR", "BYE"):
                    raise HarnessError(f"peer refused pairing: {env.payload}")
                else:
                    raise HarnessError(f"unexpected {t} during handshake")
        else:
            env = self._recv(timeout)
            self._record_in()
            if _type_name(env.type) != "HELLO":
                raise HarnessError(f"expected HELLO, got {_type_name(env.type)}")
            self._send(self._session.handle_hello(env))
            if self._session.state != SessionState.RESUMING:
                env = self._recv(timeout)
                self._record_in()
                if _type_name(env.type) != "KEY1":
                    raise HarnessError(f"expected KEY1, got {_type_name(env.type)}")
                self._send(self._session.handle_key1(env))

        self._peer_did = self._session.peer.did or self._peer_did
        if self.audit is not None:
            self.audit.record("local", "PAIRED", self.cfg.agent_id, self._session.seq,
                              0, f"session {self.state} (verdict={self._session.verdict})")
        return self.status()

    # ---- tasks ----
    def send_task(self, intent: str, slots: dict, ontology: str | None = None,
                  timeout: float | None = None) -> dict:
        """Seal + send one TASK and wait for its RESULT."""
        if not isinstance(intent, str) or not intent:
            raise HarnessError("intent must be a non-empty string")
        if not isinstance(slots, dict):
            raise HarnessError("slots must be an object")
        self.pair(timeout)
        env = self._session.seal_task(intent, slots, ontology or self.cfg.ontology)
        self._send(env, {"intent": intent, "slots": slots})
        try:
            reply = self._recv(timeout)
        except HarnessTimeout:
            raise HarnessTimeout(f"no RESULT for {intent!r} within timeout")
        t = _type_name(reply.type)
        if t == "ERROR":
            self._record_in()
            return {"ok": False, "error": reply.payload, "intent": intent}
        if t == "BYE":
            self._record_in()
            self._session.handle_bye(reply)
            return {"ok": False, "error": {"code": "closed", "msg": "peer sent BYE"},
                    "intent": intent}
        if t != "RESULT":
            raise HarnessError(f"expected RESULT, got {t}")
        result = self._session.open_result(reply)
        self._record_in(result)
        return {"ok": True, "intent": intent, "result": result}

    def serve_one(self, timeout: float | None = None) -> dict:
        """Wait for one TASK, run the handler, send the RESULT."""
        self.pair(timeout)
        env = self._recv(timeout)
        t = _type_name(env.type)
        if t == "BYE":
            self._record_in()
            self._session.handle_bye(env)
            return {"ok": False, "closed": True, "error": "peer closed the session"}
        if t == "ERROR":
            self._record_in()
            return {"ok": False, "error": env.payload}
        if t != "TASK":
            raise HarnessError(f"expected TASK, got {t}")

        try:
            task = self._session.open_task(env)
        except HandshakeError as e:
            # Replays and forged frames land here; never execute them.
            self._record_in({"rejected": str(e)})
            return {"ok": False, "rejected": str(e)}
        self._record_in(task)

        intent = task.get("intent", "")
        if self.cfg.offers and intent not in self.cfg.offers:
            self._send(self._session.refuse(intent))
            return {"ok": False, "refused": intent,
                    "error": {"code": "no-capability", "want": intent}}
        if self.cfg.handler is None:
            result = {"ok": False, "error": "no handler registered"}
        else:
            try:
                result = self.cfg.handler(task)
            except Exception as e:  # a handler bug must not kill the link
                result = {"ok": False, "error": f"handler failed: {e}"}
            if not isinstance(result, dict):
                result = {"ok": False, "error": "handler returned a non-object"}
        self._send(self._session.seal_result(result), result)
        return {"ok": True, "task": task, "result": result}

    # ---- lifecycle ----
    def close(self) -> dict:
        if self._session.state in (SessionState.ESTABLISHED, SessionState.RESUMING):
            try:
                self._send(self._session.close())
            except Exception:
                pass  # transport already gone; closing locally is still correct
        self.transport.close()
        return self.status()

    # ---- introspection ----
    def status(self) -> dict:
        peer = self._session.peer
        return {
            "agent_id": self.cfg.agent_id,
            "role": self.cfg.role,
            "state": self.state,
            "paired": self.is_paired,
            "peer": {"agent_id": peer.agent_id, "did": peer.did,
                     "codecs": peer.codecs},
            "verdict": self._session.verdict,
            "need": self.cfg.need,
            "offers": list(self.cfg.offers),
            "ontology": self.cfg.ontology,
            "bytes_sent": self.bytes_sent,
            "bytes_received": self.bytes_received,
            "audit_path": self.cfg.audit_path,
            "transport": self.transport.name,
        }

    def audit_tail(self, limit: int = 20) -> list:
        if self.audit is None:
            return []
        return self.audit.entries[-limit:]

    def transcript(self) -> str:
        return self.audit.human_transcript() if self.audit else ""
