# Architecture

```
┌─────────────┐   frames    ┌─────────────┐
│ SaphirSession│──HELLO──▶  │ SaphirSession│
│  "caller"    │◀─WELCOME── │"receptionist"│
│              │──KEY1───▶  │              │
│  crypto:     │◀─KEY2───  │  crypto:     │
│  X25519eph   │           │  X25519eph   │
│  HKDF→ChaCha │═TASK⇄════ │  HKDF→ChaCha │
└──────┬───────┘  RESULT   └──────┬───────┘
       │ audit.record()          │ audit.record()
       ▼                         ▼
   logs/demo.jsonl (sidecar, human-readable)
```

## Modules (`src/saphir/`)

- **`protocol.py`** — `Envelope` dataclass, `MsgType` enum, CBOR encode/decode with
  `u32be` length prefix, `MAX_MSG_BYTES` enforcement, `build_hello` / `build_task`.
- **`session.py`** — `SaphirSession` state machine
  (`IDLE → HELLO_SENT → KEY_SENT → ESTABLISHED → CLOSED`), `HandshakeError`,
  `seal_task/open_task/seal_result/open_result`.
- **`crypto.py`** — `EphemeralKeypair` (X25519), `derive_session_keys` (HKDF-SHA256),
  `SessionKeys.seal/open` (ChaCha20Poly1305 + replay set). Deliberately not full MLS.
- **`channel.py`** — `InMemoryChannel` (FIFO, default), `LossyChannel` wrapper
  (drop_p / corrupt_p for robustness evals), `try_ggwave_roundtrip()` probe that
  degrades gracefully when the `ggwave` package is absent.
- **`agents.py`** — rule-based `CallerAgent` / `ReceptionistAgent`, `INVENTORY`,
  `ENGLISH_SCRIPT` (Act 1) vs `STRUCTURED_TASKS` (Act 2).
- **`audit.py`** — `AuditLog`: JSONL append + `human_transcript()` renderer.
- **`metrics.py`** — `DialogueMetrics`: token/$/latency model with documented
  assumptions (chars/token, TTS/STT/LLM prices, ggwave goodput 32 Bps audible-fast).

## Data flow (demo)

`demo/demo_cli.py`: builds two sessions + two channels, pumps frames through
`encode → channel → decode → handle`, drives the hotel booking (check then book),
then runs Act 3 (forgery + replay attacks). Every step calls `audit.record()`.
