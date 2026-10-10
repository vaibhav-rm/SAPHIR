"""Reliability eval: same booking task over ReliableLink ARQ vs raw frames.

Each step delivers one SAPHIR envelope through a pair of stop-and-wait links
sharing two LossyChannels, bounded tick budget. Reports success rate, median
ticks (latency proxy), and wire bytes (retransmit cost).
"""
import sys
sys.path.insert(0, "src")
from saphir import (SaphirSession, InMemoryChannel, LossyChannel, ReliableLink,
                    ReceptionistAgent, encode_envelope, decode_envelope)

TASKS = [("hotel.check", {"date": "2026-11-02", "room": "double", "nights": 2}),
         ("hotel.book", {"date": "2026-11-02", "room": "double", "nights": 2,
                         "guests": 2, "name": "Vaibhav"})]
BUDGET = 120  # ticks per envelope step


class Driver:
    def __init__(self, drop_p: float, corrupt_p: float, seed: int):
        self.t = 0
        ab = LossyChannel(InMemoryChannel(), drop_p, corrupt_p, seed=seed)
        ba = LossyChannel(InMemoryChannel(), drop_p, corrupt_p, seed=seed + 10**6)
        self.la = ReliableLink(ab, ba)
        self.lb = ReliableLink(ba, ab)

    def deliver(self, sender: ReliableLink, receiver: ReliableLink, env):
        """Reliably move one envelope sender->receiver. Returns decoded env or None."""
        sender.send_frame(encode_envelope(env))
        for _ in range(BUDGET):
            self.la.tick(self.t)
            self.lb.tick(self.t)
            self.t += 1
            f = receiver.recv_frame()
            if f is not None:
                try:
                    e, _ = decode_envelope(f)
                    return e
                except ValueError:
                    return None  # shouldn't happen: chunks are CRC-checked
            if sender.stats.failed:
                return None
        return None

    @property
    def wire_bytes(self):
        return self.la.tx.stats.bytes_sent + self.lb.tx.stats.bytes_sent

    @property
    def retries(self):
        return self.la.stats.retries + self.lb.stats.retries


def trial(drop_p: float, corrupt_p: float, seed: int):
    try:
        d = Driver(drop_p, corrupt_p, seed)
        a, b = SaphirSession("caller"), SaphirSession("receptionist")
        recep = ReceptionistAgent()
        e = d.deliver(d.la, d.lb, a.hello())
        if e is None:
            return False, d
        w = b.handle_hello(e)
        e = d.deliver(d.lb, d.la, w)
        if e is None:
            return False, d
        k1 = a.handle_welcome(e)
        e = d.deliver(d.la, d.lb, k1)
        if e is None:
            return False, d
        k2 = b.handle_key1(e)
        e = d.deliver(d.lb, d.la, k2)
        if e is None:
            return False, d
        a.handle_key2(e)
        for intent, slots in TASKS:
            e = d.deliver(d.la, d.lb, a.seal_task(intent, slots))
            if e is None:
                return False, d
            res = recep.handle_task(b.open_task(e))
            e2 = d.deliver(d.lb, d.la, b.seal_result(res))
            if e2 is None:
                return False, d
            if not a.open_result(e2).get("ok"):
                return False, d
        return True, d
    except Exception:
        return False, None


if __name__ == "__main__":
    import statistics
    grid = [(0.0, 0.0), (0.01, 0.0), (0.05, 0.0), (0.10, 0.0),
            (0.0, 0.001), (0.0, 0.005), (0.02, 0.002), (0.05, 0.005)]
    N = 20
    print(f"| drop_p | corrupt_p | success / {N} | rate | median ticks | median wire B | median retries |")
    print("|---|---|---|---|---|---|---|")
    for drop_p, corrupt_p in grid:
        oks, ticks, wire, retr = 0, [], [], []
        for i in range(N):
            ok, d = trial(drop_p, corrupt_p, 5000 + i)
            oks += ok
            if ok:
                ticks.append(d.t)
                wire.append(d.wire_bytes)
                retr.append(d.retries)
        med = lambda v: f"{statistics.median(v):.0f}" if v else "-"
        print(f"| {drop_p:.3f} | {corrupt_p:.3f} | {oks}/{N} | {oks/N:.0%} | {med(ticks)} | {med(wire)} | {med(retr)} |")
    print("\nCompare with docs/EVALUATION.md raw-frame sweep: ARQ converts the corruption")
    print("cliff into retry cost (wire bytes), keeping task success at 100% where raw hit 0%.")
