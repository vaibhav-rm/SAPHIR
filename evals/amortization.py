"""Amortization: one 609B handshake, then how do cost/time/bytes scale with turns?

Compares, per dialogue length N:
- English-over-tones (Gibberlink-style): ~54B wire + full STT->LLM->TTS per turn.
- SAPHIR: handshake once + compact TASK/RESULT per turn, CPU-only decode.

Outputs a markdown table, CSV, and paper/figures/amortization.png.
All $/time assumptions live in saphir.metrics and are stated, not hidden.
"""
import csv
import sys
sys.path.insert(0, "src")
from saphir import SaphirSession, ReceptionistAgent, encode_envelope, decode_envelope
from saphir.agents import run_booking_dialogue
from saphir.metrics import DialogueMetrics, GGWAVE_GOODPUT_BPS

# Stated assumptions (see docs/EVALUATION.md §6):
ENGLISH_CHARS_PER_TURN = run_booking_dialogue()[0] / 4          # 214/4 ≈ 53.5
ENGLISH_TONE_BYTES_PER_TURN = round(ENGLISH_CHARS_PER_TURN)     # 1B/char, raw text
SAPHIR_CPU_USD_PER_TURN = 0.00002  # nominal CPU decode; ~100x below neural path
SAPHIR_PROC_SEC_PER_TURN = 0.4

TURN_TEMPLATES = [
    ("hotel.check", {"date": "2026-11-02", "room": "double", "nights": 2}),
    ("hotel.book", {"date": "2026-11-02", "room": "double", "nights": 2,
                    "guests": 2, "name": "Vaibhav"}),
    ("hotel.check", {"date": "2026-11-03", "room": "single", "nights": 1}),
    ("hotel.book", {"date": "2026-11-03", "room": "single", "nights": 3,
                    "guests": 1, "name": "Ram"}),
]
CANNED_RESULTS = [
    {"ok": True, "price": 120, "left": 3, "quote": 240},
    {"ok": True, "confirmation": "HB-2026-1142", "total": 240},
    {"ok": True, "price": 80, "left": 5, "quote": 80},
    {"ok": True, "confirmation": "HB-2026-1143", "total": 240},
]


def measure():
    """Returns (handshake_bytes, [turn_wire_bytes]) measured from live sessions."""
    a, b = SaphirSession("caller"), SaphirSession("receptionist")
    hs = 0
    h = a.hello(); hs += len(encode_envelope(h))
    w = b.handle_hello(decode_envelope(encode_envelope(h))[0]); hs += len(encode_envelope(w))
    k1 = a.handle_welcome(w); hs += len(encode_envelope(k1))
    k2 = b.handle_key1(k1); hs += len(encode_envelope(k2))
    a.handle_key2(k2)
    turns = []
    for i in range(20):
        intent, slots = TURN_TEMPLATES[i % len(TURN_TEMPLATES)]
        t = a.seal_task(intent, slots)
        r = b.seal_result(CANNED_RESULTS[i % len(CANNED_RESULTS)])
        turns.append(len(encode_envelope(t)) + len(encode_envelope(r)))
    return hs, turns


def english_turn_cost():
    m = DialogueMetrics(english_chars=ENGLISH_CHARS_PER_TURN, saphir_bytes=0, n_turns=1)
    return m.speech_cost_usd, m.speech_loop_seconds


def rows(hs, turns, n_max=20):
    eng_usd, eng_sec = english_turn_cost()
    out, cum_saphir_wire = [], hs
    for n in range(1, n_max + 1):
        tb = turns[n - 1]
        cum_saphir_wire += tb
        out.append({
            "turns": n,
            "eng_wire_B": ENGLISH_TONE_BYTES_PER_TURN * n,
            "saphir_wire_B": cum_saphir_wire,
            "eng_cost_usd": eng_usd * n,
            "saphir_cost_usd": SAPHIR_CPU_USD_PER_TURN * n,
            "eng_sec": eng_sec * n,
            "saphir_sec": (tb / GGWAVE_GOODPUT_BPS + SAPHIR_PROC_SEC_PER_TURN)
                           + (out[-1]["saphir_sec"] if out else hs / GGWAVE_GOODPUT_BPS),
        })
    return out


def main():
    hs, turns = measure()
    data = rows(hs, turns)
    print(f"measured: handshake={hs}B, mean turn wire={sum(turns)/len(turns):.0f}B, "
          f"english text={ENGLISH_CHARS_PER_TURN:.1f} chars/turn")
    print("| turns | eng wire B | saphir wire B | eng cost $ | saphir cost $ | eng sec | saphir sec |")
    print("|---|---|---|---|---|---|---|---|")
    for r in data:
        if r["turns"] in (1, 2, 4, 8, 12, 20):
            print(f"| {r['turns']} | {r['eng_wire_B']} | {r['saphir_wire_B']} | "
                  f"{r['eng_cost_usd']:.4f} | {r['saphir_cost_usd']:.5f} | "
                  f"{r['eng_sec']:.1f} | {r['saphir_sec']:.1f} |")
    with open("evals/amortization.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
        w.writeheader()
        w.writerows(data)
    print("wrote evals/amortization.csv")
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        xs = [r["turns"] for r in data]
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.2))
        ax1.plot(xs, [r["eng_cost_usd"] * 100 for r in data], marker="o", label="English speech loop")
        ax1.plot(xs, [r["saphir_cost_usd"] * 100 for r in data], marker="s", label="SAPHIR")
        ax1.set_xlabel("dialogue turns")
        ax1.set_ylabel("cumulative cost (US cents, modeled)")
        ax1.legend(fontsize=8)
        ax2.plot(xs, [r["eng_wire_B"] for r in data], marker="o", label="English text-over-tones")
        ax2.plot(xs, [r["saphir_wire_B"] for r in data], marker="s", label="SAPHIR (incl. handshake)")
        ax2.set_xlabel("dialogue turns")
        ax2.set_ylabel("cumulative wire bytes (measured)")
        ax2.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig("paper/figures/amortization.png", dpi=150)
        print("wrote paper/figures/amortization.png")
    except ImportError:
        print("matplotlib missing: skipped figure")


if __name__ == "__main__":
    main()
