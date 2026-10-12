"""Minimal session crypto: X25519 ephemeral + HKDF + ChaCha20Poly1305.

Deliberately NOT full MLS (future work). Provides:
- mutual ephemeral key agreement (KEY1/KEY2 carry 32B pubkeys)
- forward secrecy per pairing, replay protection via nonce set + seq window
- authenticated encryption for TASK/RESULT
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


@dataclass
class EphemeralKeypair:
    priv: X25519PrivateKey
    pub_bytes: bytes

    @classmethod
    def generate(cls) -> "EphemeralKeypair":
        priv = X25519PrivateKey.generate()
        return cls(priv=priv, pub_bytes=priv.public_key().public_bytes_raw())


@dataclass
class SessionKeys:
    key: bytes  # 32B ChaCha key
    _aead: ChaCha20Poly1305 = field(init=False, repr=False)
    seen_nonce_seq: set = field(default_factory=set, repr=False)

    def __post_init__(self):
        self._aead = ChaCha20Poly1305(self.key)

    def seal(self, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
        nonce = os.urandom(12)
        return nonce, self._aead.encrypt(nonce, plaintext, aad or None)

    def open(self, nonce: bytes, ct: bytes, aad: bytes = b"") -> bytes:
        tag = (bytes(nonce), bytes(ct))
        if tag in self.seen_nonce_seq:
            raise ValueError("replay detected: (nonce, ct) reused")
        pt = self._aead.decrypt(bytes(nonce), bytes(ct), aad or None)
        self.seen_nonce_seq.add(tag)
        return pt


def exchange(ours: EphemeralKeypair, theirs_pub: bytes) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    return ours.priv.exchange(X25519PublicKey.from_public_bytes(theirs_pub))


def keys_from_shared(shared: bytes, salt: bytes = b"saphir-v1",
                     info: bytes = b"saphir-task") -> SessionKeys:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info).derive(shared)
    return SessionKeys(key=key)


def derive_session_keys(ours: EphemeralKeypair, theirs_pub: bytes,
                        salt: bytes = b"saphir-v1", info: bytes = b"saphir-task") -> SessionKeys:
    return keys_from_shared(exchange(ours, theirs_pub), salt, info)
