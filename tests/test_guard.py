import sys
import time
sys.path.insert(0, "src")
from saphir import SaphirSession, HandshakeError, HandshakeGuard, is_fresh
from saphir import encode_envelope, decode_envelope


def _pair(**kw):
    a = SaphirSession("caller", need="hotel.book")
    b = SaphirSession("receptionist", offers=["hotel.check", "hotel.book"], **kw)
    return a, b


def test_fresh_hello_accepted():
    a, b = _pair()
    h = a.hello()
    w = b.handle_hello(decode_envelope(encode_envelope(h))[0])
    assert w.type == "WELCOME"


def test_stale_hello_rejected():
    a, b = _pair(max_skew_s=300)
    h = a.hello()
    h.payload["ts"] = int(time.time()) - 3600  # 1h old capture replayed
    try:
        b.handle_hello(h)
        assert False, "stale HELLO should be rejected"
    except HandshakeError as e:
        assert "stale" in str(e)


def test_future_hello_rejected():
    a, b = _pair(max_skew_s=300)
    h = a.hello()
    h.payload["ts"] = int(time.time()) + 3600
    try:
        b.handle_hello(h)
        assert False, "far-future HELLO should be rejected"
    except HandshakeError:
        pass


def test_freshness_disabled_when_none():
    a, b = _pair(max_skew_s=None)
    h = a.hello()
    h.payload["ts"] = int(time.time()) - 10_000
    w = b.handle_hello(h)  # opt-out: accepted
    assert w.type == "WELCOME"


def test_is_fresh_boundary():
    now = time.time()
    assert is_fresh(now, 300, now) is True
    assert is_fresh(now - 301, 300, now) is False
    assert is_fresh(now + 301, 300, now) is False


def test_guard_rate_limits_flood():
    g = HandshakeGuard(max_hellos=3, window_s=60.0)
    assert [g.allow("spk", now=1000 + i) for i in range(3)] == [True, True, True]
    assert g.allow("spk", now=1003) is False  # 4th within window refused
    assert g.refused == 1
    assert g.allow("other", now=1003) is True  # per-sender isolation
    assert g.allow("spk", now=1100) is True  # window slides, admitted again


def test_session_uses_guard():
    g = HandshakeGuard(max_hellos=1, window_s=60.0)
    a, b = _pair(guard=g)
    b.handle_hello(a.hello())  # first ok
    try:
        b.handle_hello(a.hello())  # immediate second from same sender
        assert False, "flood should be rate-limited"
    except HandshakeError as e:
        assert "rate-limited" in str(e)


def test_bye_closes_both_sides():
    a = SaphirSession("caller")
    b = SaphirSession("receptionist", offers=["hotel.check"])
    bye = a.close()
    assert a.state.value == "CLOSED"
    assert bye.type == "BYE"
    b.handle_bye(decode_envelope(encode_envelope(bye))[0])
    assert b.state.value == "CLOSED"
