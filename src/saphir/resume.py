"""Session resumption: skip KEY1/KEY2 on return visits.

After a full pairing both sides store (psk, ticket_id) under the peer's
STABLE deployment identity (ephemeral per-session DIDs rotate and can never
resume — documented tradeoff). Next HELLO to a known peer carries
{resume: ticket_id, cr: client_random}; a WELCOME echoing {resumed, sr}
completes pairing with keys = HKDF(psk, cr || sr) — fresh every visit.

Security notes (also in the manuscript):
- Resumption authenticates IMPLICITLY on first TASK (AEAD open). A responder
  enters RESUMING, not ESTABLISHED, until the first successful open.
- Tickets expire by time (ttl) and uses (max_uses); unknown/expired tickets
  fall back to a full handshake silently.
- PSK compromise affects resumed sessions only; traffic keys stay fresh.
- An attacker replaying a ticket without the PSK derives nothing: its first
  TASK fails the AEAD open and is dropped.
"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .crypto import SessionKeys, derive_session_keys


def hkdf(secret: bytes, info: bytes, n: int = 32,
         salt: bytes = b"saphir-v1") -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=n, salt=salt,
                info=info).derive(secret)


def ticket_id(psk: bytes) -> bytes:
    return hkdf(psk, b"ticket-id", 8)


def ticket_from_shared(shared: bytes) -> tuple[bytes, bytes]:
    """Returns (psk, ticket_id); both sides derive identical values."""
    psk = hkdf(shared, b"resumption-psk")
    return psk, ticket_id(psk)


def resumed_keys(psk: bytes, cr: bytes, sr: bytes) -> SessionKeys:
    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
    key = hkdf(psk, b"resumed-keys:" + bytes(cr) + bytes(sr))
    return SessionKeys(key=key)


@dataclass
class Ticket:
    psk: bytes
    peer_did: str
    created: float = field(default_factory=time.time)
    uses: int = 0


class TicketStore:
    def __init__(self, ttl_seconds: float = 3600.0, max_uses: int = 3):
        self.ttl = ttl_seconds
        self.max_uses = max_uses
        self._t: dict[str, Ticket] = {}

    def put(self, peer_did: str, psk: bytes):
        self._t[peer_did] = Ticket(psk=psk, peer_did=peer_did)

    def get(self, peer_did: str) -> Ticket | None:
        t = self._t.get(peer_did)
        if t is None:
            return None
        if time.time() - t.created > self.ttl or t.uses >= self.max_uses:
            self._t.pop(peer_did, None)
            return None
        return t

    def use(self, peer_did: str):
        t = self._t.get(peer_did)
        if t is not None:
            t.uses += 1
            if t.uses >= self.max_uses:
                self._t.pop(peer_did, None)

    def __len__(self):
        return len(self._t)


# Re-exported for session.py (avoids a circular import).
__all__ = ["Ticket", "TicketStore", "ticket_id", "ticket_from_shared",
           "resumed_keys", "derive_session_keys", "hkdf", "os"]
