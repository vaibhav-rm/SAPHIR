# Quickstart

From zero to two agents exchanging an authenticated, encrypted task in about
five minutes. No audio hardware, API keys, or network services required for the
default path.

## Requirements

- Python **3.11+** (CI runs 3.11; the repo is developed on 3.14)
- A terminal
- Optional: a browser with a microphone for the over-air web demo
- Optional: [Ollama](https://ollama.com/) or any OpenAI-compatible local server
  for the model-driven harness

## 1. Install

```bash
git clone https://github.com/vaibhav-rm/SAPHIR.git
cd SAPHIR
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The core install is small: `cbor2`, `cryptography`, `pytest`, and the optional
`ggwave` codec. Everything below runs without `ggwave`.

## 2. Prove the install

```bash
PYTHONPATH=src python -m pytest tests/ -q
PYTHONPATH=src python evals/attacks.py
```

Expected tail:

```text
60 passed
[PASS] replay: replay rejected (seq reused)
[PASS] forgery: forgery rejected ()
[PASS] downgrade: downgrade flagged: peer lacks saphir codec, staying in English
```

## 3. Run the three-act CLI demo

```bash
PYTHONPATH=src python demo/demo_cli.py
```

The demo speaks English first, pairs over SAPHIR, exchanges two encrypted
tasks, then runs the attacker:

```text
=== ACT 2: 'you're AI? switch to SAPHIR' ===
  handshake done: ESTABLISHED both sides (X25519 + ChaCha)
  [beep 117B] TASK hotel.check {...}
  [beep 131B] TASK hotel.book {...}
=== ACT 3: attacker without keys tries to hijack ===
  BLOCKED forgery as designed: InvalidTag
  BLOCKED replay as designed: replay: seq 4 reused
[PASS] replay / forgery / downgrade
```

An audit sidecar is written to `logs/demo.jsonl`. Open it and follow every
frame — that file is the point of the project as much as the crypto is.

## 4. Try the over-air web demo

This is the real thing: vendored official ggwave WASM, microphone capture,
FSK tones, and a working replay/forge attack panel.

```bash
cd demo/web
python3 -m http.server 8080
```

Open `http://localhost:8080/?role=caller` on one device and
`http://localhost:8080/?role=receptionist` on another. Both need microphone
permission. On a single device, `?role=both` loops audio through the speaker
and microphone.

Headless logic check (no mic needed):

```bash
node demo/web/smoke-test.mjs
```

## 5. Pair two processes

The harness gives you a service side and a model side over TCP, with no audio
involved:

```bash
# terminal 1 — advertises capabilities, runs the hotel handler
PYTHONPATH=src python -m saphir.harness serve \
  --agent hotel-bot --offers hotel.check,hotel.book \
  --handler hotel --listen 127.0.0.1:9001

# terminal 2 — deterministic client, no model
PYTHONPATH=src python - <<'PY'
from saphir.harness import HarnessConfig, SaphirHarness, TcpTransport

h = SaphirHarness(HarnessConfig(
    "caller-ai", role="initiator", need="hotel.book",
    transport=TcpTransport.connect("127.0.0.1", 9001),
    audit_path="logs/caller.jsonl"))

print(h.pair()["state"])
print(h.send_task("hotel.book", {
    "date": "2026-11-02", "room": "double", "nights": 2, "name": "Vaibhav"}))
h.close()
PY
```

## 6. Put a local model behind it

The model never touches keys or the wire. It sees six tools and gets JSON
results back:

```bash
PYTHONPATH=src python -m saphir.harness agent \
  --agent caller-ai --need hotel.book \
  --goal "Book a double room for 2026-11-02, 2 nights, 2 guests" \
  --backend ollama --model qwen2.5:1.5b \
  --connect 127.0.0.1:9001 \
  --audit logs/caller-ai.jsonl
```

For llama.cpp, LM Studio, or vLLM, use the OpenAI-compatible backend:

```bash
--backend openai --base-url http://localhost:8080/v1 --model <model-id>
```

No native tool calling? Wrap a text model:

```bash
--backend prompted --model qwen2.5:1.5b
```

## What just happened

| Step | Wire cost | Notes |
|---|---:|---|
| HELLO | ~107–130 B | agent id, ephemeral DID, codecs, need |
| WELCOME | ~132 B | selected codec, capability verdict |
| KEY1 + KEY2 | ~107 + 113 B | X25519 ephemerals, HKDF derives the session key |
| TASK | 117–139 B | encrypted CBOR intent + slots |
| RESULT | 126–139 B | encrypted CBOR result |

All frames fit a single audible ggwave transmission. Return visits can skip
KEY1/KEY2 using a resumption ticket.

## Next steps

- [Protocol wire format](PROTOCOL.md) — exact envelope and message payloads
- [Local-AI harness](HARNESS.md) — transports, backends, tool schemas, guardrails
- [Evaluation](EVALUATION.md) — what is measured, modeled, and still unknown
- [FAQ](FAQ.md) — the questions reviewers ask first

!!! tip "Troubleshooting"
    - `ModuleNotFoundError: saphir` — commands assume `PYTHONPATH=src` from the
      repo root.
    - `timeout waiting for a frame` — the peer is not running, or one side is
      on the wrong transport/role.
    - `cannot reach http://localhost:11434` — Ollama is not running.
    - `HTTP 404` from a local model server — the base URL needs `/v1`.
    - No microphone in the web demo — use `localhost` or HTTPS; LAN IPs are not
      secure contexts.
