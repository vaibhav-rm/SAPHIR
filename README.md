# SAPHIR — Secure Acoustic Pairing for Heterogeneous Inter-agent Rendezvous

> From spoken dialogue to auditable structured collaboration over a low-bandwidth acoustic channel.

Voice AI agents today talk to each other the wasteful way: `speech → text → LLM → speech`,
even when both sides are machines. [Gibberlink](https://github.com/PennyroyalTea/gibberlink)
(viral hackathon demo, Feb 2025) showed two agents can detect each other and switch to
`ggwave` data-over-sound tones — but with **no authentication, no negotiation, no structure,
no audit trail**. Anyone with a speaker can spoof it.

**SAPHIR** is the missing layer: a 3-phase authenticated handshake
(`HELLO → WELCOME → KEY1 → KEY2`) followed by encrypted structured tasks
(`TASK ↔ RESULT`), plus a human-readable sidecar log so every beep stays inspectable.

```
Caller (AI) ──English──▶ Receptionist (AI)     [Act 1: wasteful STT→LLM→TTS loop]
      │ "you're AI? let's switch to SAPHIR"
      ══ HELLO → WELCOME → KEY1 → KEY2 ══       [pairing, X25519 ephemeral]
      ══ TASK ⇄ RESULT (CBOR + ChaCha20Poly1305) [Act 2: structured, ~100-200B/msg]
      ✕ forged TASK rejected (InvalidTag)        [Act 3: attacker without keys]
      ✕ replayed TASK rejected (seq reuse)
      📜 sidecar audit log renders every beep human-readable
```

## Why not just…

| System | Channel | Auth | Negotiation | Auditability |
|---|---|---|---|---|
| Gibberlink (ggwave raw) | audio only | ❌ prompt only | ❌ hardcoded | ❌ beeps are opaque |
| MCP (Anthropic) | HTTPS agent→tool | ✅ | ✅ tools | ✅ |
| A2A (Google) | HTTPS agent→agent | ✅ | ✅ Agent Cards | ✅ |
| InterSAGE (2026) | HTTPS trust layer | ✅✅ | ✅ | ✅ |
| **SAPHIR (this repo)** | **audio / hybrid** | ✅ ephemeral X25519 | ✅ codec select | ✅ sidecar transcript |

MCP/A2A/InterSAGE all assume IP + HTTPS. SAPHIR covers the gap they leave:
**voice-only calls, PSTN-constrained trunks, offline / air-gapped rooms, noisy speakers.**

## Quickstart (no speakers needed)

```bash
pip install -r requirements.txt

# 3-act demo: talk → switch → attack blocked
PYTHONPATH=src python demo/demo_cli.py

# tests / benchmark / attacks / robustness sweep
PYTHONPATH=src python -m pytest tests/ -q
PYTHONPATH=src python evals/bench.py
PYTHONPATH=src python evals/attacks.py
PYTHONPATH=src python evals/robustness.py
PYTHONPATH=src python evals/reliability.py   # ARQ vs raw comparison
PYTHONPATH=src python evals/amortization.py  # cost/time/bytes vs turns + figure
PYTHONPATH=src:evals python evals/codec_profiles.py  # burst-profile sweep
```

Expected output (measured on this machine):

```
=== ACT 2: 'you're AI? switch to SAPHIR' ===
  handshake done: ESTABLISHED both sides (X25519 + ChaCha)
  [beep 182B] TASK hotel.check {...}
  [beep 202B] TASK hotel.book {...}
=== ACT 3: attacker without keys tries to hijack ===
  BLOCKED forgery as designed: InvalidTag
  BLOCKED replay as designed: replay: seq 4 reused
[PASS] replay / forgery / downgrade
```

## Protocol in 60 seconds

See [`docs/PROTOCOL.md`](docs/PROTOCOL.md) for the wire spec,
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for module design,
[`docs/EVALUATION.md`](docs/EVALUATION.md) for numbers and threat model,
[`paper/bluesky/main.pdf`](paper/bluesky/main.pdf) for the Blue Sky draft.

1. **HELLO** `A→B`: `{agent_id, did:key:ephemeral, codecs, modes, nonce, ts}` (plaintext)
2. **WELCOME** `B→A`: same + `selected` codec (negotiation; legacy peers offering no
   `saphir-cbor-v1` are flagged — no silent downgrade to beeps)
3. **KEY1 / KEY2**: 32B X25519 ephemeral pubkeys each way →
   `HKDF-SHA256 → 32B ChaCha20Poly1305` session key (forward secrecy per pairing)
4. **TASK / RESULT**: `ChaCha(cbor({intent, slots, ontology, ts}))`, AAD binds sender,
   seq + (nonce, ct) set rejects replays
5. **Sidecar**: every frame appended to JSONL with human summary + decrypted view

Frame: `u32be len ‖ CBOR({v, type, seq, sender, nonce, payload})`, cap 200B.
Measured: HELLO ~194B, KEY ~107-113B, TASK ~180-202B, RESULT ~126-139B
(≈1–2 ggwave audible transmissions per message).

## Security properties (MVP)

✅ Confidentiality + integrity for TASK/RESULT (AEAD, sender-bound AAD)
✅ Forward secrecy per pairing (ephemerals discarded)
✅ Replay rejection (seq window + nonce/ct set)
✅ Downgrade flagging (no beeps with legacy peers)
❌ **Not yet:** PKI-backed DID auth, full MLS groups, ultrasound, DoS MAC —
explicitly listed as future work (see EVALUATION.md).

## Project layout

```
src/saphir/
  protocol.py   CBOR envelope, framing, 200B cap
  session.py    handshake state machine + AEAD messaging
  crypto.py     X25519 + HKDF + ChaCha20Poly1305
  channel.py    InMemory / Lossy(drop+corrupt) / ggwave probe
  agents.py     hotel-booking toy task (English vs structured)
  audit.py      JSONL sidecar log + human transcript
  metrics.py    cost/latency model (assumptions documented)
demo/demo_cli.py   3-act demo (no audio HW required)
evals/bench.py     goodput + cost comparison
evals/attacks.py   replay / forgery / downgrade checks
tests/             pytest suite
docs/              PROTOCOL / ARCHITECTURE / EVALUATION
```

## Roadmap

- [x] Weeks 1–2: baseline (ggwave framing + booking task + metrics)
- [x] Weeks 3–4: handshake + crypto + audit + CLI demo (this release, `v0.1.0`)
- [ ] Weeks 5–6: browser demo (WebRTC + spectrogram) + lossy-channel sweep
- [ ] Weeks 7–8: 4-page workshop paper (NeurIPS AABA4ET / TAAI 2026) + arXiv
- Future: real ggwave-over-air tests, compact slot encoding, DID PKI, MLS groups

## References

- Starkov & Pidkuiko, GibberLink, 2025 — `github.com/PennyroyalTea/gibberlink`
- Ehtesham et al., Survey of MCP/ACP/A2A/ANP, arXiv:2505.02279
- Li et al., A2ASecBench, ICLR 2026
- Zou et al., InterSAGE, arXiv:2608.13030
- Dangol, Communication-Graph Metadata, arXiv:2606.07150
- Kong et al., Survey of Agent Communication Security, arXiv:2506.19676

## License

MIT (same as Gibberlink/ggwave lineage). See `LICENSE` when added.
Research prototype — not audited for production use.
