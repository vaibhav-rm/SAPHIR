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
| SAPHIR handshake (one-time) | 459 B |
| SAPHIR tasks (2 intents + 2 results, compact encoding) | 494 B (tasks alone 248 B) |
| TASK hotel.check / hotel.book wire size | 117 B / 131 B (was 182/202 B full-form) |
| TASK taxi.request / taxi.book wire size | 128 B / 139 B (non-default ontology) |
| Speech-loop wall time (model) | ~20.1 s |
| SAPHIR wall time @32 Bps (model) | ~8.6 s (tasks) / ~17.0 s (incl. handshake) |

**Claim discipline:** raw bytes are currently *larger* than English chars
(CBOR + 16B auth tags + envelope overhead). The saving is **neural compute**
(no TTS/STT/LLM forward passes per turn; tone decode is ms of CPU), not raw
byte count. Byte-compaction for tasks has landed (all task frames single-frame,
117--139 B); every frame including handshake (~115--128 B) fits one transmission.

Model assumptions live in `src/saphir/metrics.py` (prices, 4 chars/token,
32 Bps audible-fast goodput). Tune and cite before submitting.

CPU cost (measured, `evals/perf.py`, N=200): ephemeral keypair 0.06ms, full
4-message handshake 0.22ms, seal 0.008ms, open 0.02ms, bloom build+query
0.009ms, ticket derive 0.008ms. Compute is negligible next to airtime —
the cost story's "ms of CPU" is really tens of microseconds.

## 3. Threat model (MVP scope)

| Attack | Gibberlink (baseline) | SAPHIR v0.1 |
|---|---|---|
| Spoof / tone injection | ✅ succeeds (no auth) | ❌ blocked (AEAD InvalidTag) |
| Replay of valid frame | ✅ succeeds | ❌ blocked (seq + nonce set) |
| Forced downgrade to beeps | ✅ silent | ❌ flagged, stays in English |
| Eavesdropping on audio | ✅ plaintext | ❌ ciphertext |
| Attacker *with* stolen session keys | n/a | ⚠️ out of scope (needs PKI rotation — future work) |
| Impostor responder (own keys, full pairing) | ✅ pairs + reads tasks, zero signal | ⚠️ demonstrated in `evals/mitm.py`; fix = PKI-bound DIDs |
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
| 0.020 | 0.002 | 4/50 | 8% |
| 0.050 | 0.005 | 0/50 | 0% |

Reading: drops degrade gracefully (each of the ~8 frames must survive); corruption
kills fast because AEAD rejects forged frames — integrity over availability, by design.
Repro: `PYTHONPATH=src python evals/robustness.py`.

## 5. Reliability framing (measured, `evals/reliability.py`, 20 trials/cell)

Stop-and-wait ARQ (`ReliableLink`: ≤110B CRC32 chunks + ACKs, ≤10 retries) over the
same grid. Ticks = link slots; wire bytes include chunk headers, ACKs, retries.

| drop_p | corrupt_p | success | rate | median ticks | median wire B | median retries |
|---|---|---|---|---|---|---|
| 0.000 | 0.000 | 20/20 | 100% | 12 | 1538 | 0 |
| 0.010 | 0.000 | 20/20 | 100% | 12 | 1538 | 0 |
| 0.050 | 0.000 | 20/20 | 100% | 14 | 1538 | 1 |
| 0.100 | 0.000 | 17/20 | 85% | 14 | 1576 | 3 |
| 0.000 | 0.001 | 19/20 | 95% | 14 | 1665 | 1 |
| 0.000 | 0.005 | 20/20 | 100% | 26 | 2552 | 8 |
| 0.020 | 0.002 | 20/20 | 100% | 17 | 1800 | 3 |
| 0.050 | 0.005 | 19/20 | 95% | 30 | 2539 | 12 |

Headline comparison: at (0.000, 0.005) and (0.050, 0.005) raw frames score
**0%** (§4) while ARQ scores **100% / 95%**, converting the corruption cliff into
measured retry cost (~1.6× wire bytes). Residual failures at 10% loss are retry
exhaustion (bounded budget), not integrity failures. Repro:
`PYTHONPATH=src python evals/reliability.py`.

## 6. Amortization (measured bytes, modeled cost/time; `evals/amortization.py`)

One 459B handshake (measured), then rotating check/book turns (mean 246B wire
per TASK+RESULT pair, measured). English baseline: 53.5 chars/turn (measured
from the dialogue script) sent as raw text-over-tones + full STT→LLM→TTS per
turn (modeled in `metrics.py`). SAPHIR turns cost nominal CPU only (stated
$2e-5/turn assumption). Time at reference 32 Bps goodput — rescale linearly
for other ggwave profiles; bytes are the hard numbers.

| turns | eng wire B | saphir wire B | eng cost $ | saphir cost $ | eng sec | saphir sec |
|---|---|---|---|---|---|---|
| 1 | 54 | 697 | 0.0013 | 0.00002 | 5.0 | 22.2 |
| 2 | 108 | 957 | 0.0027 | 0.00004 | 10.0 | 30.7 |
| 4 | 216 | 1447 | 0.0053 | 0.00008 | 20.1 | 46.8 |
| 8 | 432 | 2431 | 0.0107 | 0.00016 | 40.2 | 79.2 |
| 20 | 1080 | 5383 | 0.0266 | 0.00040 | 100.4 | 176.2 |

Reading for the paper: **cost breakeven is immediate and grows (~65× at 20
turns)** — that, plus determinism and security, is the claimed win.
**Wall-clock is deliberately not claimed**: narrowband audio moves fewer
bytes/sec than speech, so SAPHIR trades time for near-zero neural compute.
Wire bytes stay above raw-text-over-tones (structure + auth tags cost);
Figure `paper/figures/amortization.png` plots both panels side by side.
Repro: `PYTHONPATH=src python evals/amortization.py` (writes CSV + figure).

## 7. Codec/noise profiles (byte-level models; `evals/codec_profiles.py`, 20 trials/cell)

`BurstChannel` (Gilbert-Elliott two-state bursts) + named `PROFILES`, full task
over ARQ. These are illustrative loss models, **not** waveform simulation —
over-air measurement across real codecs (PCM/Opus/G.711) remains future work,
and the manuscript must say so.

| profile | success | rate | median ticks | median wire B | median retries |
|---|---|---|---|---|---|
| clean | 20/20 | 100% | 12 | 1538 | 0 |
| cafe-noise | 19/20 | 95% | 12 | 1538 | 0 |
| opus-like | 19/20 | 95% | 12 | 1538 | 0 |
| pstn-harsh | 16/20 | 80% | 15 | 1691 | 2 |

Reading: ARQ holds ≥95% through bursty VoIP-like conditions at zero retry cost
in the median; the harsh narrowband profile degrades to 80% via retry
exhaustion, bounding the current design's operating envelope. Repro:
`PYTHONPATH=src:evals python evals/codec_profiles.py`.

## 8. Generality: second domain (taxi dispatch)

`TaxiDispatch` + `TAXI_TASKS` (`taxi.request`/`taxi.book` with fare/ETA) run the
same seal/open/handle path with a non-default ontology tag (`st1`) and
domain-specific value shorts. All four task frames across both domains fit the
single-frame budget (117/131/128/139 B). Test: `tests/test_domains.py`.
Dictionary coding is demo-scale by design; schema-driven dictionaries
negotiated in HELLO are the scalable version (manuscript RQ).

## 9. Decoder characterization (negative result, `evals/decoder_fragility.py`)

| case | input | result | meaning |
|---|---|---|---|
| clean whole-buffer | int16 direct | PASS | baseline |
| +quantization | int16 via f32 | PASS | LSB churn ok |
| rescaled 0.5x | int16 | FAIL | marker keys on absolute level |
| +40dB AWGN | int16 | FAIL | single-shot fragile |

Perturbed waveforms fed single-shot in-process fail deterministically in both
the Python and WASM builds, while real streaming over-air exchange works —
so in-process SNR sweeps would measure harness artifacts, not the channel.
Consequences applied: loss models stay byte-level and labeled as such;
demo retry is load-bearing; true room validation needs real rooms.

## 10. Impostor responder (`evals/mitm.py`, expected-insecure)

An impostor offering the same capabilities completes the identical handshake,
reaches ESTABLISHED with verdict `exact`, decrypts the booking TASK, and
answers convincingly — the caller sees no distinguishing signal. This is the
PKI gap made runnable: the future PKI upgrade's regression test must flip this
demo from "MITM DEMONSTRATED" to blocked. Repro:
`PYTHONPATH=src python evals/mitm.py`.

## 11. Capability discovery (`src/saphir/caps.py`, `tests/test_caps.py`)

HELLO carries the initiator's need plus either side's offers: a 1-byte exact
bitmask over the registered intents and a 10-byte bloom filter for open
vocabularies. Cost: HELLO 107B bare / 113B with need / 130B with offers —
still single-frame. Measured bloom FPR with 4 inserted capabilities: 5/2000
= 0.25% (theory ≈0.27%). Matching is three-valued: `exact` (bit set),
`maybe` (bloom hit only — earns a TASK attempt, never execution), `no`
(definite absence — responder's WELCOME verdict lets the caller decline fast;
a stray post-handshake TASK gets a plaintext `ERROR/no-capability`).
Verified flows: exact match, fast decline (`taxi.book` vs hotel-only host),
and maybe-confirm for unregistered (`photos.print`) capabilities.
Repro: `PYTHONPATH=src:evals python -m pytest tests/test_caps.py -q`.

## 12. Session resumption (`src/saphir/resume.py`, `tests/test_resume.py`)

Full pairing stores (psk, ticket_id) under the peer's stable deployment DID
(ephemeral per-session DIDs rotate and can never resume — documented tradeoff).
Return HELLO carries `{resume, cr}`; matching WELCOME echoes `{resumed, sr}`;
traffic keys = HKDF(psk, cr || sr), fresh every visit. Responder enters
RESUMING and only reaches ESTABLISHED on the first successful AEAD open, so
resumption authenticates implicitly. Tickets expire by TTL and uses (default 3);
unknown/expired tickets fall back to a full handshake silently.

Measured: resumed pairing costs HELLO+WELCOME = 273B vs 451B full (~40% saved,
2 frames not 4). Verified: abbreviated success with task flow, silent fallback,
expiry-forced full handshake, and keyless-attacker rejection verified.
Repro: `PYTHONPATH=src:evals python -m pytest tests/test_resume.py -q`.

## 13. Real-AI integration (`src/saphir/llm.py`, `demo/ai_dialogue.py`)
Two qwen2.5:1.5b instances (local Ollama, temperature 0) hold the English
opening, then pair and transact over SAPHIR — measured end run: switch on
timeout (small model skipped the AI-mention), exact-verdict pairing in 465B,
LLM-planned check ($120, 3 left) then book (confirmed HB-2026-1142), LLM
narration, 12s total, 973B on the wire. Design rules: planning output is
validated/coerced (unknown intents fall back, never reach the wire);
inventory stays deterministic (LLM plans and narrates, never touches state).
Mock-backed tests (`tests/test_llm.py`) cover coercion hardening, both switch
paths, and the full dialogue with zero inference. Repro (needs Ollama):
`PYTHONPATH=src python demo/ai_dialogue.py --backend ollama`.

## 14. Handshake admission guard (`src/saphir/guard.py`, `tests/test_guard.py`)

Plaintext HELLOs are cheap to forge, so responders now enforce two
front-door policies (both opt-in, zero wire-format change): HELLO
freshness (±300 s default, `max_skew_s=None` disables) rejects replayed
stale/future captures before any crypto, and `HandshakeGuard`
(per-sender token bucket, default 5 HELLOs/60 s) refuses floods before
key agreement. Graceful `close()`/`handle_bye()` moves both sides to
CLOSED. Repro: `PYTHONPATH=src python -m pytest tests/test_guard.py -q`.
