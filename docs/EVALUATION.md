# Evaluation

## 1. Functionality (all passing)

```
PYTHONPATH=src python -m pytest tests/ -q        # 3 passed
PYTHONPATH=src python evals/attacks.py
# [PASS] replay: replay rejected (seq reused)
# [PASS] forgery: forgery rejected (InvalidTag)
# [PASS] downgrade: peer lacks saphir codec → stays in English, flagged
```

## 2. Efficiency — honest numbers (measured, `evals/bench.py`)

| Metric | Value |
|---|---|
| English dialogue | 214 chars (~54 tokens) |
| SAPHIR handshake (one-time) | 609 B |
| SAPHIR tasks (2 intents + 2 results) | 630 B (tasks alone 384 B) |
| Speech-loop wall time (model) | ~20.1 s |
| SAPHIR wall time @32 Bps (model) | ~13.6 s (tasks) / ~41 s (incl. handshake) |

**Claim discipline:** raw bytes are currently *larger* than English chars
(CBOR + 16B auth tags + envelope overhead). The saving is **neural compute**
(no TTS/STT/LLM forward passes per turn; tone decode is ms of CPU), not raw
byte count. Handshake amortizes over longer dialogues. Byte-compaction
(short slot keys, array-form CBOR) is scheduled work — do not claim byte
savings in the paper until it lands.

Model assumptions live in `src/saphir/metrics.py` (prices, 4 chars/token,
32 Bps audible-fast goodput). Tune and cite before submitting.

## 3. Threat model (MVP scope)

| Attack | Gibberlink (baseline) | SAPHIR v0.1 |
|---|---|---|
| Spoof / tone injection | ✅ succeeds (no auth) | ❌ blocked (AEAD InvalidTag) |
| Replay of valid frame | ✅ succeeds | ❌ blocked (seq + nonce set) |
| Forced downgrade to beeps | ✅ silent | ❌ flagged, stays in English |
| Eavesdropping on audio | ✅ plaintext | ❌ ciphertext |
| Attacker *with* stolen session keys | n/a | ⚠️ out of scope (needs PKI rotation — future work) |
| Traffic analysis (who talks) | n/a | ⚠️ out of scope (see Dangol 2026) |

## 4. Robustness (next)

`LossyChannel(drop_p, corrupt_p)` exists for codec/noise sweeps
(PCM / Opus / G.711, 0–20 dB SNR). Sweep script + tables are weeks 5–6 work.
