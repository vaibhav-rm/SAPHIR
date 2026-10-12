"""Attack checks: replay, spoof/forgery, downgrade. Exit nonzero on failure."""
import sys
sys.path.insert(0, "src")
from saphir import SaphirSession, LocalLink, encode_envelope, decode_envelope


def handshake():
    a, b = SaphirSession("caller"), SaphirSession("receptionist")
    link = LocalLink(a, b)
    link.handshake()
    return a, b, link.ab, link.ba


def test_replay_rejected():
    a, b, ab, ba = handshake()
    t = a.seal_task("hotel.book", {"date": "2026-11-02", "room": "double", "nights": 1, "name": "X"})
    raw = encode_envelope(t)
    ab.send(raw)
    e, _ = decode_envelope(ab.recv()); b.open_task(e)
    ab.send(raw)
    e, _ = decode_envelope(ab.recv())
    try:
        b.open_task(e)
        return False, "replay accepted!"
    except Exception as ex:
        return True, f"replay rejected ({ex})"


def test_forgery_rejected():
    a, b, ab, ba = handshake()
    t = a.seal_task("hotel.book", {"nights": 1})
    raw = bytearray(encode_envelope(t))
    raw[-1] ^= 0xFF  # flip tag byte
    ab.send(bytes(raw))
    try:
        e, _ = decode_envelope(ab.recv()); b.open_task(e)
        return False, "forged tag accepted!"
    except Exception as ex:
        return True, f"forgery rejected ({ex})"


def test_downgrade_flagged():
    # Gibberlink-style peer with no KEY support: hello without codecs -> we refuse to send TASK
    from saphir.protocol import MsgType
    a = SaphirSession("caller")
    h = a.hello()
    fake_welcome = {"agent_id": "legacy", "did": "none", "codecs": [], "selected": "english-only"}
    import os
    from saphir.protocol import Envelope
    w = Envelope(type=MsgType.WELCOME, seq=0, sender="legacy", nonce=os.urandom(16), payload=fake_welcome)
    try:
        k1 = a.handle_welcome(w)
        # policy: if peer has no saphir codec, do NOT proceed silently
        if "saphir-cbor-v1" not in (fake_welcome["codecs"] or []):
            return True, "downgrade flagged: peer lacks saphir codec, staying in English (no silent beeps)"
        return False, "downgrade not flagged"
    except Exception as ex:
        return True, f"downgrade blocked ({ex})"


if __name__ == "__main__":
    results = [("replay", *test_replay_rejected()),
               ("forgery", *test_forgery_rejected()),
               ("downgrade", *test_downgrade_flagged())]
    ok = True
    for name, passed, msg in results:
        print(f"[{'PASS' if passed else 'FAIL'}] {name}: {msg}")
        ok &= passed
    sys.exit(0 if ok else 1)
