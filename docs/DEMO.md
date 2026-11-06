# Demos

Three ways to see SAPHIR run: a real over-air browser demo, a terminal demo,
and a local-model demo. All of them use the same protocol and the same audit
story.

## Web demo — real ggwave over air

Two agents hold a short English call, detect each other, then switch to genuine
FSK tone bursts carrying ECDH + AES-GCM-encrypted tasks. Replay and forge
buttons really fail.

```bash
cd demo/web
python3 -m http.server 8080
```

| URL | Role |
|---|---|
| `http://localhost:8080/` | role picker |
| `?role=caller` | initiator |
| `?role=receptionist` | responder |
| `?role=both` | both roles on one device, speaker → mic loopback |

Requirements: microphone permission and a secure context. `localhost` counts as
secure; two LAN devices need HTTPS.

### What is real

- **Transport.** Vendored official ggwave WASM; every frame is really
  FSK-modulated and decoded from the microphone. Audible-fastest profile,
  ≤138 B frames, Reed–Solomon on the wire, TX gain dialed for ears.
- **Crypto.** ECDH P-256 + AES-GCM via WebCrypto, fresh IVs per message, replay
  sets mirroring `src/saphir/`.
- **Reliability.** Response-driven retransmission: every reply is also the ACK.
  Retries re-seal with fresh IVs, so a poisoned payload is never replayed.
- **Attacks.** Replay re-transmits captured tones and is rejected by sequence
  sets. Forge flips a ciphertext byte with a fresh sequence number and is
  rejected by AES-GCM.
- **English.** Spoken with browser TTS.

### Headless verification

```bash
node demo/web/smoke-test.mjs
```

Drives both sessions through loopback delivery with real crypto, injects one
TASK loss (retry must recover it), then runs all four attacks. Must print
`SMOKE OK`.

!!! note "Demo-grade by design"
    The web demo uses JSON framing (the protocol uses CBOR), illustrative DIDs,
    and two parties only. The reference protocol implementation is `src/saphir/`.
    Frame shapes are regression-guarded by `evals/ggwave_frames.py` against the
    real Python ggwave build.

## CLI demo — three acts, no hardware

```bash
PYTHONPATH=src python demo/demo_cli.py
```

| Act | What happens |
|---|---|
| 1 | Caller and receptionist talk in English — the wasteful STT → LLM → TTS loop |
| 2 | Pairing: HELLO → WELCOME → KEY1 → KEY2, then encrypted TASK/RESULT |
| 3 | An attacker without keys attempts forgery, replay, and downgrade — all blocked |

Writes `logs/demo.jsonl`. Inspect it with any JSONL viewer or the
`AuditLog.human_transcript()` helper.

## AI dialogue — two real local models

```bash
PYTHONPATH=src python demo/ai_dialogue.py --backend ollama
PYTHONPATH=src python demo/ai_dialogue.py --backend mock   # no model needed
```

Two Ollama `qwen2.5:1.5b` instances hold the English opening, decide to switch,
then plan and book over SAPHIR. Planning output is validated and coerced before
it reaches the wire; tool execution stays deterministic.

## Local-AI harness

```bash
PYTHONPATH=src python -m saphir.harness demo
```

Two in-process agents, a scripted model on the caller side, the deterministic
hotel handler on the service side, and a full tool trace. Add
`--audit logs/demo.jsonl` to capture the sidecar.

For the two-process version, see [Quickstart](quickstart.md) and the
[harness guide](HARNESS.md).

## What the demos deliberately do not show

- Real-room acoustics across devices and distances (future work).
- A PSTN or Opus-compressed trunk carrying the tones.
- PKI-backed agent identity — the impostor-responder break is documented in
  `evals/mitm.py`.
- Groups larger than two.

Those are research open items, not hidden demo assumptions.
