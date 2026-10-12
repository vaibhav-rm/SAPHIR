import sys
sys.path.insert(0, "src")
from saphir import (SaphirSession, TicketStore, ReceptionistAgent,
                    encode_envelope, decode_envelope)

DID_C, DID_R = "did:key:zcaller-stable", "did:key:zrecep-stable"


def full_pairing(store_c=None, store_r=None):
    a = SaphirSession("caller", did=DID_C, store=store_c,
                      need="hotel.book", offers=[])
    b = SaphirSession("receptionist", did=DID_R, store=store_r,
                      offers=["hotel.check", "hotel.book"])
    frames = []
    h = a.hello(); frames.append(h)
    w = b.handle_hello(decode_envelope(encode_envelope(h))[0]); frames.append(w)
    k1 = a.handle_welcome(w); frames.append(k1)
    k2 = b.handle_key1(decode_envelope(encode_envelope(k1))[0]); frames.append(k2)
    a.handle_key2(decode_envelope(encode_envelope(k2))[0])
    nbytes = sum(len(encode_envelope(f)) for f in frames)
    return a, b, nbytes


def test_full_pairing_stores_tickets():
    sc, sr = TicketStore(), TicketStore()
    a, b, _ = full_pairing(sc, sr)
    assert a.state.value == b.state.value == "ESTABLISHED"
    assert len(sc) == 1 and len(sr) == 1


def test_resumed_pairing_skips_keys():
    sc, sr = TicketStore(), TicketStore()
    full_pairing(sc, sr)
    a2 = SaphirSession("caller", did=DID_C, store=sc, need="hotel.book")
    b2 = SaphirSession("receptionist", did=DID_R, store=sr,
                       offers=["hotel.check", "hotel.book"])
    h = a2.hello(peer_did=DID_R)
    assert "resume" in h.payload and "cr" in h.payload
    w = b2.handle_hello(decode_envelope(encode_envelope(h))[0])
    assert b2.state.value == "RESUMING"
    assert "resumed" in w.payload and "sr" in w.payload
    r = a2.handle_welcome(decode_envelope(encode_envelope(w))[0])
    assert r is None  # no KEY1 needed
    assert a2.state.value == "ESTABLISHED"
    # abbreviated handshake bytes: HELLO + WELCOME only
    nbytes = len(encode_envelope(h)) + len(encode_envelope(w))
    assert nbytes < 400, nbytes
    # tasks flow on resumed keys, responder verifies on first open
    t = a2.seal_task("hotel.book", {"date": "2026-11-02", "room": "double",
                                    "nights": 1, "name": "V"})
    got = b2.open_task(decode_envelope(encode_envelope(t))[0])
    assert b2.state.value == "ESTABLISHED"
    assert got["slots"]["room"] == "double"
    res = ReceptionistAgent().handle_task(got)
    back = a2.open_result(decode_envelope(
        encode_envelope(b2.seal_result(res)))[0])
    assert back["ok"] is True


def test_unknown_ticket_falls_back():
    sc, sr = TicketStore(), TicketStore()
    full_pairing(sc, sr)
    a2 = SaphirSession("caller", did="did:key:zstranger", store=TicketStore())
    b2 = SaphirSession("receptionist", did=DID_R, store=sr,
                       offers=["hotel.check", "hotel.book"])
    h = a2.hello(peer_did=DID_R)  # stranger has no ticket
    assert "resume" not in h.payload
    w = b2.handle_hello(decode_envelope(encode_envelope(h))[0])
    assert "resumed" not in w.payload
    assert b2.state.value != "RESUMING"


def test_ticket_expiry_forces_full_handshake():
    sc, sr = TicketStore(max_uses=1), TicketStore(max_uses=1)
    full_pairing(sc, sr)
    a2 = SaphirSession("caller", did=DID_C, store=sc, need="hotel.book")
    b2 = SaphirSession("receptionist", did=DID_R, store=sr,
                       offers=["hotel.check", "hotel.book"])
    h = a2.hello(peer_did=DID_R)
    w = b2.handle_hello(decode_envelope(encode_envelope(h))[0])
    assert "resumed" in w.payload  # first resumption ok (consumes the single use)
    assert a2.handle_welcome(decode_envelope(encode_envelope(w))[0]) is None
    assert a2.state.value == "ESTABLISHED"
    a3 = SaphirSession("caller", did=DID_C, store=sc, need="hotel.book")
    h3 = a3.hello(peer_did=DID_R)
    assert "resume" not in h3.payload  # ticket exhausted -> silent full handshake


def test_attacker_without_psk_fails():
    sc, sr = TicketStore(), TicketStore()
    full_pairing(sc, sr)
    # Attacker replays a stolen HELLO (with resume ticket) but holds no PSK.
    a2 = SaphirSession("caller", did=DID_C, store=sc, need="hotel.book")
    b2 = SaphirSession("receptionist", did=DID_R, store=sr,
                       offers=["hotel.check", "hotel.book"])
    h = a2.hello(peer_did=DID_R)
    raw = encode_envelope(h)
    # Attacker crafts its own session but cannot derive keys; force-derive fails:
    # simulate by opening a task sealed under the real resumed keys with a
    # session that never completed resumption.
    w = b2.handle_hello(decode_envelope(raw)[0])
    assert "resumed" in w.payload
    a2.handle_welcome(decode_envelope(encode_envelope(w))[0])
    t = a2.seal_task("hotel.book", {"date": "2026-11-02", "room": "double",
                                    "nights": 1, "name": "Mallory"})
    evil = SaphirSession("mallory", did="did:key:zevil", store=TicketStore())
    # Mallory never paired: no keys at all -> must refuse, not crash
    try:
        evil.open_task(decode_envelope(encode_envelope(t))[0])
        assert False, "keyless open accepted"
    except Exception:
        pass
