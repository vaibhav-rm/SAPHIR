import sys
sys.path.insert(0, "src")
from saphir import SaphirSession, encode_envelope, decode_envelope


def _handshake():
    a, b = SaphirSession("caller"), SaphirSession("receptionist")
    h = a.hello()
    w = b.handle_hello(decode_envelope(encode_envelope(h))[0])
    k1 = a.handle_welcome(w)
    k2 = b.handle_key1(k1)
    a.handle_key2(k2)
    return a, b


def test_cbor_roundtrip():
    a, b = _handshake()
    t = a.seal_task("hotel.check", {"date": "2026-11-02"})
    env, _ = decode_envelope(encode_envelope(t))
    got = b.open_task(env)
    assert got["intent"] == "hotel.check"


def test_frame_sizes_fit_ggwave():
    a, b = _handshake()
    for intent, slots in [("hotel.check", {"date": "2026-11-02", "room": "double", "nights": 2}),
                          ("hotel.book", {"date": "2026-11-02", "room": "double", "nights": 2, "name": "V"})]:
        assert len(encode_envelope(a.seal_task(intent, slots))) <= 200


def test_version_rejected():
    import cbor2
    from saphir.protocol import LEN_PREFIX
    bad = LEN_PREFIX.pack(0) if False else None
    raw = cbor2.dumps({"v": 999, "type": "HELLO", "seq": 0, "sender": "x", "nonce": b"0" * 16, "payload": {}})
    import struct
    buf = struct.pack(">I", len(raw)) + raw
    try:
        decode_envelope(buf)
        assert False, "should reject"
    except ValueError:
        pass
