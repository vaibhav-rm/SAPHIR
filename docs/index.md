---
title: SAPHIR
hide:
  - navigation
  - toc
---

# SAPHIR

Secure acoustic pairing for AI agents on a voice-only channel.

SAPHIR is a small, auditable protocol for two AI agents that share nothing but an
audio channel. It replaces the wasteful speech loop (speech → text → LLM → speech)
with a short authenticated handshake followed by compact, encrypted structured
intents.

The protocol has four phases:

- **HELLO → WELCOME** — capability and codec negotiation
- **KEY1 → KEY2** — ephemeral X25519 key exchange
- **TASK ↔ RESULT** — encrypted CBOR intents and results
- **Audit** — every frame lands in a human-readable JSONL sidecar

Frames are capped at 200 bytes and fit inside a single audible ggwave transmission.
The core library runs without any audio hardware, so pairing and testing also work
over loopback, shared directories, or TCP.

## Start here

- [Quickstart](quickstart.md) — install, run the demo, and inspect the audit log
- [Wire format](PROTOCOL.md) — frame layout and message types
- [Local-AI harness](HARNESS.md) — attach SAPHIR to any local model
- [Evaluation](EVALUATION.md) — measured numbers and threat model
- [FAQ](FAQ.md) — scope, limitations, and what is missing

!!! note "Research prototype"
    SAPHIR v0.1 is not audited and is not ready for production use. It has no
    PKI-backed identity and no group sessions. Read the FAQ and Status & roadmap
    before deploying anything.
