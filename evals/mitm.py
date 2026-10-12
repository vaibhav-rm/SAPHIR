"""Impostor-responder demonstration (expected-insecure, documented on purpose).

With an unauthenticated handshake, NOTHING stops this: an impostor offering
hotel.* completes the full pairing with a caller and decrypts its booking
TASK. The caller sees zero distinguishing signal (verdict exact, states
ESTABLISHED). This is precisely the PKI gap declared out of scope — here made
concrete and runnable, so the future PKI upgrade has a regression test that
must FLIP to blocked.

Exit 0 always: informational threat demo, like decoder_fragility.
"""
import sys
sys.path.insert(0, "src")
from saphir import (SaphirSession, ReceptionistAgent,
                    encode_envelope, decode_envelope)


def main() -> int:
    caller = SaphirSession("caller", need="hotel.book")
    impostor = SaphirSession("evil-receptionist",
                             offers=["hotel.check", "hotel.book"])

    # Identical API to an honest pairing — that is the vulnerability.
    h = caller.hello()
    w = impostor.handle_hello(decode_envelope(encode_envelope(h))[0])
    k1 = caller.handle_welcome(w)
    k2 = impostor.handle_key1(k1)
    caller.handle_key2(k2)

    print(f"caller state      : {caller.state.value} (verdict={caller.verdict})")
    print(f"impostor state    : {impostor.state.value}")
    print(f"caller peer       : {caller.peer.agent_id} {caller.peer.did}")
    print(f"impostor peer     : {impostor.peer.agent_id} {impostor.peer.did}")
    print("distinguishing signal for caller: NONE (no PKI)")

    task = caller.seal_task("hotel.book", {"date": "2026-11-02", "room": "double",
                                           "nights": 2, "guests": 2, "name": "Vaibhav"})
    raw = encode_envelope(task)
    env, _ = decode_envelope(raw)
    stolen = impostor.open_task(env)  # attacker holds session keys: AEAD opens
    print(f"impostor recovers : {stolen['intent']} {stolen['slots']}")

    # And the impostor can answer, so the caller never suspects:
    res = ReceptionistAgent().handle_task(stolen)
    back = impostor.seal_result(res)
    env2, _ = decode_envelope(encode_envelope(back))
    got = caller.open_result(env2)
    print(f"caller believes   : ok={got['ok']} confirmation={got.get('confirmation')}")
    print("MITM DEMONSTRATED — fix = PKI-bound DIDs (see docs/publication-plan.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
