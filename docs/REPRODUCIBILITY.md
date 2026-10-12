# Reproducibility appendix

Artifact: \url{https://github.com/vaibhav-rm/SAPHIR} (MIT, research prototype).

## Environment
- Python 3.14, `pip install -r requirements.txt` (`cbor2`, `cryptography`, `pytest`).
- LaTeX (TeX Live) only needed for `paper/`; `matplotlib` only for the amortization figure.
- No audio hardware, no API keys, no network needed. All channels are in-process
  byte pipes; `channel.try_ggwave_roundtrip()` degrades gracefully without `ggwave`.

## Commands (run from repo root)
| Claim | Command |
|---|---|
| Unit tests (11) | `PYTHONPATH=src:evals python -m pytest tests/ -q` |
| 3-act demo + audit log | `PYTHONPATH=src python demo/demo_cli.py` (writes `logs/demo.jsonl`) |
| Cost/goodput bench | `PYTHONPATH=src python evals/bench.py` |
| Attack matrix | `PYTHONPATH=src python evals/attacks.py` (exit nonzero on failure) |
| Raw robustness sweep | `PYTHONPATH=src python evals/robustness.py` |
| ARQ reliability sweep | `PYTHONPATH=src python evals/reliability.py` |
| Codec/noise profiles | `PYTHONPATH=src:evals python evals/codec_profiles.py` |
| Decoder characterization | `PYTHONPATH=src python evals/decoder_fragility.py` |
| Impostor demo (expected-break) | `PYTHONPATH=src python evals/mitm.py` |
| Amortization + figure | `PYTHONPATH=src python evals/amortization.py` (writes `evals/amortization.csv`, `paper/figures/amortization.png`) |
| Blue Sky draft | `cd paper/bluesky && pdflatex main.tex` (twice) |
| Journal manuscript | `cd paper/journal && pdflatex main.tex` (twice) |

## Seeds and determinism
- `robustness.py`: 50 trials/cell, channel seeds `1000+i`.
- `reliability.py`: 20 trials/cell, seeds `5000+i` (peer link `+10**6`).
- `codec_profiles.py`: 20 trials/cell, seeds `9000+i`.
- Ephemeral X25519 keys use `os.urandom` (fresh per pairing, as in deployment);
  all reported rates are over the stated trial counts, not single runs.
- `tests/` use fixed seeds and pass deterministically.

## What is modeled vs measured
- **Measured:** all byte sizes (live CBOR envelopes), handshake/task flows, attack
  outcomes, sweep success rates, retry/tick counts.
- **Modeled (stated assumptions in `src/saphir/metrics.py`):** $ costs (TTS/STT/LLM
  list prices), speech timing (14 chars/s + 1.2 s inference/turn), 32 Bps
  reference goodput, nominal CPU cost per SAPHIR turn. Wall-time rescales
  linearly with goodput; byte counts do not depend on these assumptions.
- **Simulated, not over-air:** `LossyChannel`/`BurstChannel` profiles are byte-level
  loss models. Waveform/room/codec measurement is explicit future work.
