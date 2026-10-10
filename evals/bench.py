"""GibberBench-lite: goodput + cost comparison Gibberlink-text vs SAPHIR-structured."""
import sys
sys.path.insert(0, "src")
from saphir import SaphirSession, InMemoryChannel, encode_envelope
from saphir.agents import ENGLISH_SCRIPT, STRUCTURED_TASKS, run_booking_dialogue
from saphir.channel import try_ggwave_roundtrip
from saphir.metrics import DialogueMetrics
from saphir.protocol import MsgType, decode_envelope


def pairing_bytes():
    a, b = SaphirSession("caller"), SaphirSession("receptionist")
    from saphir import ReceptionistAgent
    recep = ReceptionistAgent()
    ab, ba = InMemoryChannel(), InMemoryChannel()
    total = 0
    for ch, sess_call in ((ab, lambda e: (b.handle_hello(e) if e.type == "HELLO" else None)),):
        pass
    # manual handshake
    h = a.hello(); ab.send(encode_envelope(h)); total += len(encode_envelope(h))
    e, _ = decode_envelope(ab.recv()); w = b.handle_hello(e); ba.send(encode_envelope(w)); total += len(encode_envelope(w))
    e, _ = decode_envelope(ba.recv()); k1 = a.handle_welcome(e); ab.send(encode_envelope(k1)); total += len(encode_envelope(k1))
    e, _ = decode_envelope(ab.recv()); k2 = b.handle_key1(e); ba.send(encode_envelope(k2)); total += len(encode_envelope(k2))
    e, _ = decode_envelope(ba.recv()); a.handle_key2(e)
    task_bytes = 0
    for t in STRUCTURED_TASKS:
        te = a.seal_task(t["intent"], t["slots"]); f = encode_envelope(te); task_bytes += len(f)
        ab.send(f)
        e, _ = decode_envelope(ab.recv()); task = b.open_task(e); res = recep.handle_task(task)
        r = b.seal_result(res); f2 = encode_envelope(r); task_bytes += len(f2)
    return total, task_bytes


if __name__ == "__main__":
    eng, _ = run_booking_dialogue()
    hs, tasks = pairing_bytes()
    m = DialogueMetrics(english_chars=eng, saphir_bytes=tasks)
    ok, msg = try_ggwave_roundtrip(b"hello")
    print("transport:", msg)
    print(f"English dialogue chars : {eng} (~{eng/4:.0f} tokens)")
    print(f"SAPHIR handshake bytes : {hs} (one-time per pairing)")
    print(f"SAPHIR task bytes      : {tasks} (2 intents + 2 results)")
    print("metrics:", m.summary())
    print(f"bytes vs chars ratio   : {tasks/eng:.2f} (lower = more efficient; + handshake amortizes over turns)")
