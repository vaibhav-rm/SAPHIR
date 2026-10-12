import sys
sys.path.insert(0, "src")
from saphir import (SaphirSession, TicketStore, LocalLink, ReceptionistAgent,
                    encode_envelope)


def test_link_handshake_and_task():
    a = SaphirSession("caller", need="hotel.book")
    b = SaphirSession("receptionist", offers=["hotel.check", "hotel.book"])
    link = LocalLink(a, b)
    n = link.handshake()
    assert a.state.value == b.state.value == "ESTABLISHED"
    assert 300 <= n <= 700, n
    assert a.verdict == "exact"
    res = link.task("hotel.book", {"date": "2026-11-02", "room": "double",
                                   "nights": 1, "name": "V"},
                    ReceptionistAgent().handle_task)
    assert res["ok"] is True and "confirmation" in res


def test_link_resumption_automatic():
    sc, sr = TicketStore(), TicketStore()
    a = SaphirSession("caller", did="did:key:zC", store=sc, need="hotel.book")
    b = SaphirSession("receptionist", did="did:key:zR", store=sr,
                      offers=["hotel.check", "hotel.book"])
    full = LocalLink(a, b).handshake()
    a2 = SaphirSession("caller", did="did:key:zC", store=sc, need="hotel.book")
    b2 = SaphirSession("receptionist", did="did:key:zR", store=sr,
                       offers=["hotel.check", "hotel.book"])
    fast = LocalLink(a2, b2).handshake()  # peer hints automatic: no KEY frames
    assert fast < full
    res = LocalLink(a2, b2).task("hotel.check", {"date": "2026-11-02", "room": "double", "nights": 1},
                                 ReceptionistAgent().handle_task)
    assert res["ok"] is True


def test_link_lossy_reports():
    from saphir import LinkError
    a = SaphirSession("caller")
    b = SaphirSession("receptionist", offers=["hotel.check"])
    link = LocalLink(a, b, drop_p=1.0, seed=0)  # total loss
    try:
        link.handshake()
        assert False, "lossy handshake should raise"
    except LinkError:
        pass
