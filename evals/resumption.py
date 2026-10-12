"""Resumption showcase: first visit pairs fully, return visit skips KEY1/KEY2.

Prints the byte comparison (paper anecdote) and runs a task on resumed keys.
Stable deployment DIDs required — ephemeral identities can never resume.
"""
import sys
sys.path.insert(0, "src")
from saphir import (SaphirSession, TicketStore, ReceptionistAgent,
                    encode_envelope, decode_envelope)

DID_C, DID_R = "did:key:zcaller-stable", "did:key:zrecep-stable"


def main() -> int:
    sc, sr = TicketStore(), TicketStore()
    print("=== visit 1: full pairing ===")
    a = SaphirSession("caller", did=DID_C, store=sc, need="hotel.book")
    b = SaphirSession("receptionist", did=DID_R, store=sr,
                      offers=["hotel.check", "hotel.book"])
    wire = []
    h = a.hello(); wire.append(("HELLO", h))
    w = b.handle_hello(decode_envelope(encode_envelope(h))[0]); wire.append(("WELCOME", w))
    k1 = a.handle_welcome(w); wire.append(("KEY1", k1))
    k2 = b.handle_key1(decode_envelope(encode_envelope(k1))[0]); wire.append(("KEY2", k2))
    a.handle_key2(decode_envelope(encode_envelope(k2))[0])
    full = sum(len(encode_envelope(e)) for _, e in wire)
    print(f"  {' + '.join(t for t, _ in wire)} = {full}B, states {a.state.value}/{b.state.value}")

    print("=== visit 2 (later): abbreviated pairing ===")
    a2 = SaphirSession("caller", did=DID_C, store=sc, need="hotel.book")
    b2 = SaphirSession("receptionist", did=DID_R, store=sr,
                       offers=["hotel.check", "hotel.book"])
    h2 = a2.hello(peer_did=DID_R)
    w2 = b2.handle_hello(decode_envelope(encode_envelope(h2))[0])
    assert "resumed" in w2.payload
    assert a2.handle_welcome(decode_envelope(encode_envelope(w2))[0]) is None
    fast = len(encode_envelope(h2)) + len(encode_envelope(w2))
    print(f"  HELLO + WELCOME = {fast}B, states {a2.state.value}/{b2.state.value}")
    print(f"  saved {full - fast}B ({100 * (full - fast) / full:.0f}%) — no KEY frames")

    t = a2.seal_task("hotel.book", {"date": "2026-11-02", "room": "double",
                                    "nights": 1, "name": "Vaibhav"})
    got = b2.open_task(decode_envelope(encode_envelope(t))[0])
    res = ReceptionistAgent().handle_task(got)
    print(f"  task on resumed keys: ok={res['ok']} confirmation={res.get('confirmation')}")
    print("RESUMPTION SHOWCASE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
