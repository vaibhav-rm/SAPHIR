import sys
sys.path.insert(0, "src")
from saphir import (SaphirSession, BloomFilter, match, encode_envelope, decode_envelope)


def _handshake(caller, recep):
    h = caller.hello()
    w = recep.handle_hello(decode_envelope(encode_envelope(h))[0])
    k1 = caller.handle_welcome(w)
    k2 = recep.handle_key1(k1)
    caller.handle_key2(k2)
    return h, w


def test_bloom_fpr_small():
    b = BloomFilter()
    for it in ["hotel.check", "hotel.book", "taxi.request", "taxi.book"]:
        b.add(it)
    assert "hotel.book" in b
    fp = sum(f"random-cap-{i}" in b for i in range(2000))
    assert fp / 2000 < 0.05, fp


def test_match_levels():
    b = BloomFilter()
    b.add("photos.print")  # open vocab only: maybe, never exact
    assert match("hotel.book", 0b11110, b) == "exact"
    assert match("photos.print", 0, b) == "maybe"
    assert match("car.repair", 0, b) == "no"


def test_handshake_carries_caps_and_fits():
    c = SaphirSession("caller", need="hotel.book")
    r = SaphirSession("receptionist", offers=["hotel.check", "hotel.book"])
    h, w = _handshake(c, r)
    assert len(encode_envelope(h)) <= 138, len(encode_envelope(h))
    assert len(encode_envelope(w)) <= 138, len(encode_envelope(w))
    assert r.peer_need == "hotel.book"
    assert c.verdict == "exact"


def test_mismatch_declines_fast():
    c = SaphirSession("caller", need="taxi.book")
    r = SaphirSession("receptionist", offers=["hotel.check", "hotel.book"])
    _handshake(c, r)
    assert c.verdict == "no"
    err = r.refuse("taxi.book")
    assert err.type == "ERROR" and err.payload["code"] == "no-capability"


def test_maybe_path_confirms():
    c = SaphirSession("caller", need="photos.print")
    r = SaphirSession("receptionist", offers=[])
    r.bloom.add("photos.print")  # heard-of capability, not in registry
    _handshake(c, r)
    assert c.verdict == "maybe"
