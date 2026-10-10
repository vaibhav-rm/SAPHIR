"""3-act SAPHIR demo (runs without speakers). Act1 English, Act2 switch, Act3 attack blocked."""
import sys
sys.path.insert(0, "src")
from saphir import (SaphirSession, InMemoryChannel, AuditLog, ReceptionistAgent,
                    encode_envelope, decode_envelope)
from saphir.agents import ENGLISH_SCRIPT, STRUCTURED_TASKS
from saphir.metrics import DialogueMetrics
from saphir.protocol import MsgType


def xfer(env, ch, audit, direction):
    frame = encode_envelope(env)
    audit.record(direction, env.type, env.sender, env.seq, len(frame),
                 f"pairing frame ({len(frame)}B)")
    ch.send(frame)


def pump(ch, sess, recep, audit, direction):
    raw = ch.recv()
    assert raw is not None
    env, _ = decode_envelope(raw)
    if env.type == MsgType.HELLO:
        w = sess.handle_hello(env)
        audit.record(direction, env.type, env.sender, env.seq, len(raw), "hello received")
        return w
    if env.type == MsgType.WELCOME:
        k1 = sess.handle_welcome(env)
        audit.record(direction, env.type, env.sender, env.seq, len(raw), "welcome, codec selected")
        return k1
    if env.type == MsgType.KEY1:
        k2 = sess.handle_key1(env)
        audit.record(direction, env.type, env.sender, env.seq, len(raw), "key1 -> session established")
        return k2
    if env.type == MsgType.KEY2:
        sess.handle_key2(env)
        audit.record(direction, env.type, env.sender, env.seq, len(raw), "key2 -> session established")
        return None
    if env.type == MsgType.TASK:
        task = sess.open_task(env)
        res = recep.handle_task(task)
        audit.record(direction, env.type, env.sender, env.seq, len(raw),
                     f"intent={task.get('intent')}", decrypted=task)
        r = sess.seal_result({**res, "for_seq": env.seq})
        audit.record("send", "RESULT", sess.agent_id, r.seq, len(encode_envelope(r)), f"ok={res.get('ok')}", decrypted=res)
        return r
    if env.type == MsgType.RESULT:
        res = sess.open_result(env)
        audit.record(direction, env.type, env.sender, env.seq, len(raw), f"result ok={res.get('ok')}", decrypted=res)
        return None
    return None


def main():
    audit = AuditLog("logs/demo.jsonl")
    import pathlib; pathlib.Path("logs/demo.jsonl").unlink(missing_ok=True)

    print("=== ACT 1: English (wasteful) ===")
    for who, line in ENGLISH_SCRIPT:
        print(f"  [{who} voice]: {line}")

    print("\n=== ACT 2: 'you're AI? switch to SAPHIR' ===")
    a, b = SaphirSession("caller"), SaphirSession("receptionist")
    recep = ReceptionistAgent()
    ab, ba = InMemoryChannel(), InMemoryChannel()

    h = a.hello(); xfer(h, ab, audit, "A->B")
    w = pump(ab, b, recep, audit, "A->B"); xfer(w, ba, audit, "B->A")
    k1 = pump(ba, a, recep, audit, "B->A"); xfer(k1, ab, audit, "A->B")
    k2 = pump(ab, b, recep, audit, "A->B"); xfer(k2, ba, audit, "B->A")
    pump(ba, a, recep, audit, "B->A")
    assert a.state.value == b.state.value == "ESTABLISHED"
    print("  handshake done: ESTABLISHED both sides (X25519 + ChaCha)")

    total = 0
    for t in STRUCTURED_TASKS:
        te = a.seal_task(t["intent"], t["slots"]); f = encode_envelope(te); total += len(f)
        print(f"  [beep {len(f)}B] TASK {t['intent']} {t['slots']}")
        xfer(te, ab, audit, "A->B")
        r = pump(ab, b, recep, audit, "A->B"); xfer(r, ba, audit, "B->A")
        pump(ba, a, recep, audit, "B->A")
    print(f"  booking confirmed over {total}B encrypted")

    from saphir.agents import run_booking_dialogue
    eng, _ = run_booking_dialogue()
    m = DialogueMetrics(english_chars=eng, saphir_bytes=total)
    print("\nMetrics:", m.summary())

    print("\n=== ACT 3: attacker without keys tries to hijack ===")
    from saphir.protocol import Envelope as _Env
    import os as _os
    # Eve never did KEY exchange: crafts a plaintext TASK-looking frame + replays old bytes
    fake = _Env(type=MsgType.TASK, seq=99, sender="caller",
                nonce=_os.urandom(12), payload=b"\x00" * 40)
    ab.send(encode_envelope(fake))
    try:
        raw_evil = ab.recv()
        env_evil, _ = decode_envelope(raw_evil)
        b.open_task(env_evil)
        print("  FAIL: forged TASK accepted (bug)")
    except Exception as e:
        print(f"  BLOCKED forgery as designed: {type(e).__name__}: {e}")

    # exact replay of an old valid frame
    evil = a.seal_task("hotel.book", {"date": "2026-11-02", "room": "double", "nights": 99, "name": "Mallory"})
    raw = encode_envelope(evil)
    ab.send(raw)
    r = pump(ab, b, recep, audit, "ATTACKER->B")
    print("  (fresh-seq attacker frame with stolen session accepted once — expected, seq is new)")
    ab.send(raw)  # exact replay
    try:
        pump(ab, b, recep, audit, "ATTACKER->B")
        print("  FAIL: replay accepted (bug)")
    except Exception as e:
        print(f"  BLOCKED replay as designed: {e}")

    print("\n--- sidecar audit (human-readable) ---")
    print(audit.human_transcript())
    print("\nDemo OK. Log: logs/demo.jsonl")


if __name__ == "__main__":
    main()
