"""Codec/noise profile sweep: full booking task over ARQ under named conditions.

Profiles are byte-level loss models (see ChannelProfile) — illustrative, not
waveform simulation. Over-air measurement across real codecs is future work.
"""
import sys
sys.path.insert(0, "src")
sys.path.insert(0, "evals")
from saphir import InMemoryChannel, BurstChannel, PROFILES
from reliability import trial


def factory_for(name):
    profile = PROFILES[name]
    def make(seed):
        ab = BurstChannel(InMemoryChannel(), profile, seed=seed)
        ba = BurstChannel(InMemoryChannel(), profile, seed=seed + 10**6)
        return ab, ba
    return make


if __name__ == "__main__":
    import statistics
    N = 20
    print("| profile | success / %d | rate | median ticks | median wire B | median retries |" % N)
    print("|---|---|---|---|---|---|---|")
    for name, p in PROFILES.items():
        oks, ticks, wire, retr = 0, [], [], []
        for i in range(N):
            ok, d = trial(0.0, 0.0, 9000 + i, factory=factory_for(name))
            oks += ok
            if ok:
                ticks.append(d.t)
                wire.append(d.wire_bytes)
                retr.append(d.retries)
        med = lambda v: f"{statistics.median(v):.0f}" if v else "-"
        print(f"| {name} | {oks}/{N} | {oks/N:.0%} | {med(ticks)} | {med(wire)} | {med(retr)} |")
    print(f"\nModel: { {k: v.note for k, v in PROFILES.items()} }")
