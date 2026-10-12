"""Decoder characterization (negative result, documented on purpose).

Feeding perturbed waveforms to ggwave single-shot in-process FAILS even at
40dB SNR — in both the Python (0.4.3) and vendored WASM builds — while real
streaming over-air exchange works (different input context: continuous stream,
AGC, adaptation). Consequences, all applied in this repo:
  1. Waveform-level SNR sweeps in-process measure harness artifacts, not the
     channel — so our loss models stay byte-level (LossyChannel/BurstChannel)
     and honest about it.
  2. The demo's response-driven retry is load-bearing, not ornamental.
  3. True room validation needs real rooms (microphone + speakers), still open.

Fast (~4 decodes), deterministic. Exit 0 always: this is a characterization,
not a gate. Requires: pip install ggwave.
"""
import sys

import numpy as np


def main() -> int:
    try:
        import ggwave
    except ImportError:
        print("SKIP: pip install ggwave first")
        return 0
    ggwave.disableLog()
    frame = '{"t":"HELLO","f":"c","did":"9f2c"}'

    def fresh():
        return ggwave.init()

    def close(inst):
        ggwave.free(inst)

    print("| case | input | result | meaning |")
    print("|---|---|---|---|")

    # 1. clean whole-buffer int16: the only in-process path that works
    inst = fresh()
    wf = ggwave.encode(frame, protocolId=1, volume=10)
    back = ggwave.decode(inst, wf)
    print(f"| clean whole-buffer | int16 direct | {'PASS' if back and back.decode() == frame else 'FAIL'} | baseline |")
    close(inst)

    # 2. unity float roundtrip (quantization only): works
    x = np.frombuffer(wf, dtype=np.int16).astype(np.float32) / 32768.0
    inst = fresh()
    back = ggwave.decode(inst, np.clip(x * 32767, -32768, 32767).astype(np.int16).tobytes())
    print(f"| +quantization | int16 via f32 | {'PASS' if back and back.decode() == frame else 'FAIL'} | LSB churn ok |")
    close(inst)

    # 3. rescaled to half peak: fails (marker threshold keys on absolute level)
    inst = fresh()
    peak = float(np.max(np.abs(x)))
    y = np.clip(x / peak * 0.5 * 32767, -32768, 32767).astype(np.int16).tobytes()
    back = ggwave.decode(inst, y)
    print(f"| rescaled 0.5x | int16 | {'PASS' if back and back.decode() == frame else 'FAIL'} | level-sensitive |")
    close(inst)

    # 4. +40dB AWGN: fails (fragile single-shot, both builds)
    inst = fresh()
    rng = np.random.default_rng(7)
    sig = float(np.mean(x ** 2))
    n = rng.normal(0.0, np.sqrt(sig / 10 ** 4), len(x)).astype(np.float32)
    back = ggwave.decode(inst, np.clip((x + n) * 32767, -32768, 32767).astype(np.int16).tobytes())
    print(f"| +40dB AWGN | int16 | {'PASS' if back and back.decode() == frame else 'FAIL'} | single-shot fragile |")
    close(inst)

    print("CHARACTERIZATION DONE (see docstring for consequences)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
