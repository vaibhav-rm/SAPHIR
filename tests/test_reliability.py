import sys
sys.path.insert(0, "src")
from saphir import (SaphirSession, InMemoryChannel, LossyChannel, ReliableLink,
                    encode_envelope, decode_envelope)


def _pair(drop=0.0, corrupt=0.0, seed=0):
    ab = LossyChannel(InMemoryChannel(), drop, corrupt, seed=seed)
    ba = LossyChannel(InMemoryChannel(), drop, corrupt, seed=seed + 1)
    return ReliableLink(ab, ba), ReliableLink(ba, ab)


def _exchange(la, lb, payload: bytes, budget=60):
    la.send_frame(payload)
    t = 0
    got = None
    while t < budget and got is None:
        la.tick(t)
        lb.tick(t)
        t += 1
        got = lb.recv_frame()
    return got


def test_reliable_delivers_clean():
    la, lb = _pair()
    assert _exchange(la, lb, b"hello-saphir") == b"hello-saphir"


def test_reliable_survives_loss():
    la, lb = _pair(drop=0.05, corrupt=0.0, seed=7)
    msg = bytes(range(256)) * 2  # 512B -> multi-chunk
    assert _exchange(la, lb, msg, budget=200) == msg


def test_reliable_recovers_corruption():
    la, lb = _pair(drop=0.0, corrupt=0.005, seed=11)
    assert _exchange(la, lb, b"task-payload-123", budget=200) == b"task-payload-123"


def test_end_to_end_task_over_arq():
    import sys
    sys.path.insert(0, "evals")
    from reliability import trial
    ok, _ = trial(0.02, 0.002, seed=42)
    assert ok
