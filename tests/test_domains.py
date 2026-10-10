import sys
sys.path.insert(0, "src")
from saphir import (SaphirSession, TaxiDispatch, TAXI_TASKS,
                    encode_envelope, decode_envelope)


def test_taxi_end_to_end():
    a, b = SaphirSession("rider"), SaphirSession("dispatch")
    h = a.hello()
    w = b.handle_hello(decode_envelope(encode_envelope(h))[0])
    k1 = a.handle_welcome(w)
    k2 = b.handle_key1(k1)
    a.handle_key2(k2)
    fleet = TaxiDispatch()
    for t in TAXI_TASKS:
        env = a.seal_task(t["intent"], t["slots"], t["ontology"])
        assert len(encode_envelope(env)) <= 140, (t["intent"], len(encode_envelope(env)))
        got = b.open_task(decode_envelope(encode_envelope(env))[0])
        assert got["slots"] == t["slots"] and got["ontology"] == t["ontology"], got
        res = fleet.handle_task(got)
        assert res["ok"] is True, res
        back = a.open_result(decode_envelope(
            encode_envelope(b.seal_result(res)))[0])
        assert back["ok"] is True


def test_hotel_book_fits_single_frame():
    a, b = SaphirSession("caller"), SaphirSession("receptionist")
    h = a.hello()
    w = b.handle_hello(decode_envelope(encode_envelope(h))[0])
    k1 = a.handle_welcome(w)
    k2 = b.handle_key1(k1)
    a.handle_key2(k2)
    t = a.seal_task("hotel.book", {"date": "2026-11-02", "room": "double",
                                   "nights": 2, "guests": 2, "name": "Vaibhav"})
    assert len(encode_envelope(t)) <= 140
    got = b.open_task(decode_envelope(encode_envelope(t))[0])
    assert got["slots"] == {"date": "2026-11-02", "room": "double", "nights": 2,
                            "guests": 2, "name": "Vaibhav"}
    assert got["ontology"] == "saphir-hotel-v1"
