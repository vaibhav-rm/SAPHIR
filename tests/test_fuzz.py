"""Hostile-input hardening: garbage must be rejected, never wedge the session.

Property under test: after ANY sequence of malformed frames, a session pair
can still complete a legitimate handshake and exchange tasks. Rejections must
raise (ValueError, KeyError, HandshakeError, TypeError, ...) — i.e. ordinary
Exceptions a caller handles — and must never corrupt session state.
"""
import os
import random
import sys
sys.path.insert(0, "src")
import cbor2
from saphir import (SaphirSession, encode_envelope, decode_envelope,
                    HandshakeError, BloomFilter)
from saphir.protocol import Envelope, MsgType

rng = random.Random(20261012)


def garbage_frames(n=300):
    outs = []
    for _ in range(n):
        kind = rng.randrange(5)
        if kind == 0:
            outs.append(os.urandom(rng.randrange(0, 300)))
        elif kind == 1:  # truncated valid frame
            e = encode_envelope(Envelope(type=MsgType.HELLO, seq=0, sender="x",
                                         nonce=b"0" * 8, payload={"did": "d"}))
            outs.append(e[:rng.randrange(0, len(e))])
        elif kind == 2:  # valid CBOR, wrong shape
            outs.append(b"\x00\x00\x00\x05" + cbor2.dumps(rng.choice(
                [[1, 2], "str", 42, {"v": 999}, {"v": 1}])))
        elif kind == 3:  # bit flips in a valid frame
            e = bytearray(encode_envelope(Envelope(
                type=MsgType.TASK, seq=7, sender="caller",
                nonce=os.urandom(12), payload=os.urandom(20))))
            for _ in range(rng.randrange(1, 4)):
                e[rng.randrange(len(e))] ^= 1 << rng.randrange(8)
            outs.append(bytes(e))
        else:  # right envelope, hostile payload types
            outs.append(encode_envelope(Envelope(
                type=rng.choice(list(MsgType)).value, seq=rng.randrange(100),
                sender="x", nonce=b"0" * 8,
                payload=rng.choice([None, 3.14, [1], {"did": ["nested"]},
                                    {"did": "d", "codec": "notalist"}])))
        )
    return outs


def test_garbage_never_wedges_sessions():
    a = SaphirSession("caller", need="hotel.book")
    b = SaphirSession("receptionist", offers=["hotel.check", "hotel.book"])
    for raw in garbage_frames():
        try:
            env, _ = decode_envelope(raw)
        except Exception:
            continue  # rejected at framing: correct
        for sess, handler in ((b, "handle_hello"), (a, "handle_welcome")):
            try:
                getattr(sess, handler)(env)
            except Exception:
                pass  # rejected at handshake: correct
        for sess in (a, b):
            try:
                sess.open_task(env)
            except Exception:
                pass  # rejected at AEAD: correct
    # ...and yet a legitimate handshake still completes afterwards.
    h = a.hello(peer_did=None)
    w = b.handle_hello(decode_envelope(encode_envelope(h))[0])
    k1 = a.handle_welcome(w)
    assert k1 is not None and k1.type == MsgType.KEY1
    k2 = b.handle_key1(decode_envelope(encode_envelope(k1))[0])
    a.handle_key2(decode_envelope(encode_envelope(k2))[0])
    t = a.seal_task("hotel.check", {"date": "2026-11-02"})
    assert b.open_task(decode_envelope(encode_envelope(t))[0])["intent"] == "hotel.check"


def test_bloom_wire_validation():
    try:
        BloomFilter.from_wire(b"\x00" * 9)
        assert False, "short bloom accepted"
    except ValueError:
        pass
    assert isinstance(BloomFilter.from_wire(b"\x00" * 10).wire(), bytes)
