"""Robustness sweep: handshake + task success over lossy acoustic channels.

Grid: drop_p x corrupt_p, N trials each. Prints a markdown table for the paper.
No retransmission in v0.1, so drops fail the handshake by design — the table
quantifies exactly how much reliability framing is needed (future work).
"""
import sys
sys.path.insert(0, "src")
from saphir import SaphirSession, InMemoryChannel, LossyChannel
from saphir import encode_envelope, decode_envelope
from saphir import ReceptionistAgent

TRIALS = 50


def trial(drop_p: float, corrupt_p: float, seed: int) -> bool:
    try:
        a, b = SaphirSession("caller"), SaphirSession("receptionist")
        recep = ReceptionistAgent()
        ab = LossyChannel(InMemoryChannel(), drop_p, corrupt_p, seed=seed)
        ba = LossyChannel(InMemoryChannel(), drop_p, corrupt_p, seed=seed + 10**6)

        def send(ch, env):
            ch.send(encode_envelope(env))

        def recv(ch):
            raw = ch.recv()
            if raw is None:
                raise IOError("frame dropped")
            env, _ = decode_envelope(raw)
            return env

        send(ab, a.hello()); w = b.handle_hello(recv(ab))
        send(ba, w); k1 = a.handle_welcome(recv(ba))
        send(ab, k1); k2 = b.handle_key1(recv(ab))
        send(ba, k2); a.handle_key2(recv(ba))

        for intent, slots in [("hotel.check", {"date": "2026-11-02", "room": "double", "nights": 2}),
                              ("hotel.book", {"date": "2026-11-02", "room": "double",
                                              "nights": 2, "guests": 2, "name": "Vaibhav"})]:
            send(ab, a.seal_task(intent, slots))
            task = b.open_task(recv(ab))
            res = recep.handle_task(task)
            send(ba, b.seal_result(res))
            got = a.open_result(recv(ba))
            assert got["ok"] is True
        return True
    except Exception:
        return False


if __name__ == "__main__":
    grid = [(0.0, 0.0), (0.01, 0.0), (0.05, 0.0), (0.10, 0.0),
            (0.0, 0.001), (0.0, 0.005), (0.02, 0.002), (0.05, 0.005)]
    print("| drop_p | corrupt_p | success / %d | rate |" % TRIALS)
    print("|---|---|---|---|")
    for drop_p, corrupt_p in grid:
        ok = sum(trial(drop_p, corrupt_p, 1000 + i) for i in range(TRIALS))
        print(f"| {drop_p:.3f} | {corrupt_p:.3f} | {ok}/{TRIALS} | {ok/TRIALS:.0%} |")
    print("\nNote: v0.1 has no retransmission; any dropped handshake frame fails the pairing.")
    print("Takeaway for paper: reliability framing (ACK/retry) is required before over-air claims.")
