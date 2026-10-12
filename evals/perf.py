"""CPU cost of SAPHIR operations (the "ms of CPU" claim, measured).

Times pure local compute — no airtime, no network. Budgets are generous
regression guards against perf rot, not targets.
"""
import sys
import timeit
sys.path.insert(0, "src")
from saphir import (SaphirSession, TicketStore, BloomFilter,
                    encode_envelope, decode_envelope)

N = 200
BUDGETS = {  # ms
    "ephemeral keypair": 20.0,
    "full handshake (4 msgs)": 50.0,
    "seal task": 5.0,
    "open task": 5.0,
    "bloom build+query": 5.0,
    "ticket derive": 5.0,
}


def bench(name, fn, n=N):
    dt = timeit.timeit(fn, number=n) / n * 1000
    ok = dt < BUDGETS[name]
    print(f"| {name} | {dt:.3f} | {BUDGETS[name]:.1f} | {'ok' if ok else 'OVER'} |")
    return ok


def main() -> int:
    from saphir import EphemeralKeypair
    from saphir.resume import ticket_from_shared
    from saphir.crypto import exchange
    print("| op | mean ms | budget ms | verdict |")
    print("|---|---|---|---|")
    ok = True
    ok &= bench("ephemeral keypair", lambda: EphemeralKeypair.generate())

    def handshake():
        a = SaphirSession("c")
        b = SaphirSession("r", offers=["hotel.check"])
        h = a.hello()
        w = b.handle_hello(decode_envelope(encode_envelope(h))[0])
        k1 = a.handle_welcome(w)
        k2 = b.handle_key1(decode_envelope(encode_envelope(k1))[0])
        a.handle_key2(decode_envelope(encode_envelope(k2))[0])
    ok &= bench("full handshake (4 msgs)", handshake)

    a = SaphirSession("c")
    b = SaphirSession("r", offers=["hotel.check"])
    h = a.hello()
    w = b.handle_hello(decode_envelope(encode_envelope(h))[0])
    k1 = a.handle_welcome(w)
    k2 = b.handle_key1(decode_envelope(encode_envelope(k1))[0])
    a.handle_key2(decode_envelope(encode_envelope(k2))[0])
    slots = {"date": "2026-11-02", "room": "double", "nights": 2}
    ok &= bench("seal task", lambda: a.seal_task("hotel.check", slots))

    def open_fresh():  # fresh seal each time: replay protection would (rightly) reject repeats
        t = a.seal_task("hotel.check", slots)
        return b.open_task(decode_envelope(encode_envelope(t))[0])
    ok &= bench("open task", open_fresh)

    def bloom():
        flt = BloomFilter()
        for it in ["hotel.check", "hotel.book", "taxi.request", "taxi.book"]:
            flt.add(it)
        return "hotel.book" in flt
    ok &= bench("bloom build+query", bloom)

    kp = EphemeralKeypair.generate()
    kp2 = EphemeralKeypair.generate()
    shared = exchange(kp, kp2.pub_bytes)
    ok &= bench("ticket derive", lambda: ticket_from_shared(shared))

    print("PERF:", "ALL OK" if ok else "OVER BUDGET")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
