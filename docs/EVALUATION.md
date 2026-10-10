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
| SAPHIR tasks (2 intents + 2 results, compact encoding) | 528 B (tasks alone 282 B) |
| TASK hotel.check / hotel.book wire size | 134 B / 148 B (was 182/202 B full-form) |
| Speech-loop wall time (model) | ~20.1 s |
| SAPHIR wall time @32 Bps (model) | ~10.4 s (tasks) / ~18 s (incl. handshake) |

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

## 4. Robustness (measured, `evals/robustness.py`, 50 trials/cell, no retransmission)

| drop_p | corrupt_p | success | rate |
|---|---|---|---|
| 0.000 | 0.000 | 50/50 | 100% |
| 0.010 | 0.000 | 47/50 | 94% |
| 0.050 | 0.000 | 35/50 | 70% |
| 0.100 | 0.000 | 22/50 | 44% |
| 0.000 | 0.001 | 18/50 | 36% |
| 0.000 | 0.005 | 0/50 | 0% |
| 0.020 | 0.002 | 5/50 | 10% |
| 0.050 | 0.005 | 0/50 | 0% |

Reading: drops degrade gracefully (each of the ~8 frames must survive); corruption
kills fast because AEAD rejects forged frames — integrity over availability, by design.
Repro: `PYTHONPATH=src python evals/robustness.py`.

## 5. Reliability framing (measured, `evals/reliability.py`, 20 trials/cell)

Stop-and-wait ARQ (`ReliableLink`: ≤110B CRC32 chunks + ACKs, ≤10 retries) over the
same grid. Ticks = link slots; wire bytes include chunk headers, ACKs, retries.

| drop_p | corrupt_p | success | rate | median ticks | median wire B | median retries |
|---|---|---|---|---|---|---|
| 0.000 | 0.000 | 20/20 | 100% | 12 | 1572 | 0 |
| 0.010 | 0.000 | 20/20 | 100% | 12 | 1572 | 0 |
| 0.050 | 0.000 | 20/20 | 100% | 14 | 1572 | 1 |
| 0.100 | 0.000 | 17/20 | 85% | 14 | 1627 | 3 |
| 0.000 | 0.001 | 19/20 | 95% | 14 | 1699 | 1 |
| 0.000 | 0.005 | 20/20 | 100% | 26 | 2523 | 8 |
| 0.020 | 0.002 | 20/20 | 100% | 17 | 1834 | 3 |
| 0.050 | 0.005 | 19/20 | 95% | 30 | 2589 | 12 |

Headline comparison: at (0.000, 0.005) and (0.050, 0.005) raw frames score
**0%** (§4) while ARQ scores **100% / 95%**, converting the corruption cliff into
measured retry cost (~1.6× wire bytes). Residual failures at 10% loss are retry
exhaustion (bounded budget), not integrity failures. Repro:
`PYTHONPATH=src python evals/reliability.py`.
