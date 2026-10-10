import sys
sys.path.insert(0, "src")
sys.path.insert(0, "evals")
from saphir import InMemoryChannel, BurstChannel, PROFILES
from reliability import trial
from codec_profiles import factory_for


def test_burst_channel_clean_passthrough():
    from saphir import ReliableLink
    ab = BurstChannel(InMemoryChannel(), PROFILES["clean"], seed=0)
    ba = BurstChannel(InMemoryChannel(), PROFILES["clean"], seed=1)
    la, lb = ReliableLink(ab, ba), ReliableLink(ba, ab)
    la.send_frame(b"ping")
    got = None
    for t in range(20):
        la.tick(t)
        lb.tick(t)
        got = lb.recv_frame()
        if got is not None:
            break
    assert got == b"ping"


def test_profile_sweep_clean_succeeds():
    ok, _ = trial(0.0, 0.0, seed=9000, factory=factory_for("clean"))
    assert ok


def test_profile_sweep_harsh_terminates():
    # Must terminate with a boolean, whatever the outcome on this seed.
    ok, d = trial(0.0, 0.0, seed=9001, factory=factory_for("pstn-harsh"))
    assert isinstance(ok, bool)
