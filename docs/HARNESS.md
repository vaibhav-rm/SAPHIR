# SAPHIR harness — attach the protocol to any local AI

The harness turns SAPHIR from a protocol library into a drop-in capability for
local models. It owns the session, transport, capability allow-list, and audit
sidecar; the model only sees six tools.

```
        ┌──────────────── your local model ────────────────┐
        │  Ollama · llama.cpp · LM Studio · vLLM · Python   │
        └───────────────────────┬──────────────────────────┘
                    tool calls  │  JSON results
        ┌───────────────────────▼──────────────────────────┐
        │  ToolBridge   pair · send_task · serve · audit    │
        │  SaphirHarness  session + allow-list + sidecar    │
        └───────────────────────┬──────────────────────────┘
             transport (bytes)  │
     loopback · shared dir · TCP · (ggwave audio in demo/web)
```

## Quickstart (no model, no hardware)

```bash
PYTHONPATH=src python -m saphir.harness demo
```

Two in-process agents pair, exchange a `hotel.check` and a `hotel.book`
TASK/RESULT pair, and print the tool trace. `--audit logs/demo.jsonl` also
writes the sidecar transcript.

## Two processes, any local model

Start the service side (it advertises two intents and runs the deterministic
hotel handler):

```bash
PYTHONPATH=src python -m saphir.harness serve \
  --agent hotel-bot --offers hotel.check,hotel.book --handler hotel \
  --listen 127.0.0.1:9001 --timeout 30
```

Then point a local model at it. The harness speaks to Ollama natively:

```bash
PYTHONPATH=src python -m saphir.harness agent \
  --agent caller-ai --need hotel.book \
  --goal "Book a double room for 2026-11-02, 2 nights, 2 guests" \
  --backend ollama --model qwen2.5:1.5b \
  --connect 127.0.0.1:9001
```

Or to any OpenAI-compatible server (llama.cpp `--api`, LM Studio, vLLM,
LocalAI). `base_url` includes the version:

```bash
PYTHONPATH=src python -m saphir.harness agent \
  --agent caller-ai --need hotel.book --goal "..." \
  --backend openai --base-url http://localhost:8080/v1 \
  --model qwen2.5-7b-instruct --connect 127.0.0.1:9001
```

No ports available? Use the shared-directory transport. Both processes point at
the same directory with mirrored inbox names:

```bash
# terminal 1
... serve --file-dir /tmp/saphir --inbox hotel --peer-inbox caller ...
# terminal 2
... agent --file-dir /tmp/saphir --inbox caller --peer-inbox hotel ...
```

## Integration levels

### 1. Model with native tool calling — `ToolBridge`

```python
from saphir.harness import SaphirHarness, HarnessConfig, ToolBridge, TcpTransport

h = SaphirHarness(HarnessConfig(
    "my-agent", role="initiator", need="hotel.book",
    transport=TcpTransport.connect("127.0.0.1", 9001),
    audit_path="logs/my-agent.jsonl"))
bridge = ToolBridge(h, outbound_intents=("hotel.book",))

tools = bridge.specs()                    # OpenAI/Ollama function schema
result = bridge.call("saphir_send_task", {  # dispatch a model's tool call
    "intent": "hotel.book",
    "slots": {"date": "2026-11-02", "room": "double", "nights": 1},
})
```

`bridge.dispatch(name, args)` returns the JSON string that chat APIs expect as
tool content.

### 2. Ready-made loop — `SaphirAgent`

```python
from saphir.harness import OllamaChatBackend, SaphirAgent

agent = SaphirAgent(OllamaChatBackend("qwen2.5:1.5b"), h,
                    outbound_intents=("hotel.book",))
run = agent.run("Book a double room for 2026-11-02.")
print(run.text)                # final answer
print(run.tool_trace)          # every tool call + result, auditable
```

The loop is bounded by `max_steps`, stops on the first turn without tool calls,
and feeds every tool result back to the model. Errors are returned as
`{"ok": false, "error": ...}` — a tool failure never aborts the loop.

### 3. Prompt-only models — `PromptedToolsBackend`

Models without function calling get the schema as text and answer with
`{"tool": "...", "args": {...}}` or `{"final": "..."}`:

```python
from saphir.harness import PromptedToolsBackend
from saphir import OllamaBackend

backend = PromptedToolsBackend.from_llm(OllamaBackend("qwen2.5:1.5b"))
agent = SaphirAgent(backend, h)
```

### 4. Your own agent loop

Use `SaphirHarness` directly and skip the model entirely:

```python
h.pair()
out = h.send_task("hotel.check", {"date": "2026-11-02", "room": "double"})
# service side:
h.serve_one()   # opens one TASK, runs cfg.handler, seals the RESULT
```

The service handler is just a callable, so it can be a local model too:

```python
import json
from saphir.harness import HarnessConfig, SaphirHarness
from saphir import OllamaBackend

llm = OllamaBackend("qwen2.5:1.5b")

def llm_handler(task: dict) -> dict:
    reply = llm.complete(
        "Answer the task as compact JSON with an 'ok' field. No prose.",
        str(task), max_tokens=120)
    return json.loads(reply)   # validate before trusting it in production

h = SaphirHarness(HarnessConfig(
    "llm-service", role="responder", offers=("hotel.check",),
    handler=llm_handler, transport=...))
```

## Tools exposed to the model

| Tool | Purpose |
|---|---|
| `saphir_status` | Link state, peer DID, capabilities, verdict, byte counters |
| `saphir_pair` | Run the handshake (auto-called before the first task) |
| `saphir_send_task` | Send one encrypted TASK, wait for its RESULT |
| `saphir_serve` | Wait for one inbound TASK, execute locally, reply |
| `saphir_audit` | Human-readable sidecar transcript |
| `saphir_close` | Send BYE and close the link |

## Guardrails (on by default)

- **Capability allow-list.** A responder only executes intents it advertised in
  HELLO. Anything else gets a plaintext `no-capability` ERROR frame, never a
  handler call. This also stops bloom-filter false positives from executing.
- **Size budget.** `saphir_send_task` rejects slots whose JSON exceeds 120 B
  before sealing, so the 200 B frame cap fails in the model's context rather
  than on the wire.
- **Handler isolation.** Handler exceptions become `{"ok": false}` results; the
  link survives.
- **Replay rejection.** Replayed TASK frames fail the sequence check inside the
  session and are answered without execution.
- **Audit.** Every frame is appended to JSONL with direction, type, size, and
  decrypted TASK/RESULT summaries when `--audit` is set.

## Resumption

Give both sides a stable `--did` to enable session resumption (HELLO/WELCOME
only, no KEY frames) for return visits in the same process. Ticket stores are
in-memory by design: persisting PSKs is a security decision left to the
deployment. Ephemeral DIDs (the default) always do a full handshake.

## What is deliberately not here

- **Audio plumbing.** The harness is transport-agnostic. The real microphone
  path is `demo/web` (vendored ggwave WASM). Bridge a sound modem to
  `Transport.send/recv` to use the harness over air.
- **Identity/PKI.** DIDs are illustrative; `evals/mitm.py` demonstrates the
  impostor-responder gap. Do not treat the harness as authenticated identity.
- **Multi-party sessions.** Two endpoints per session, matching protocol v0.1.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `cannot reach http://...` | Ollama/llama.cpp not running, or wrong host/port |
| `HTTP 404` from the model | OpenAI-compatible `base_url` missing `/v1` |
| `timeout: waiting for a frame` | Peer not started, wrong transport pair, or role swapped |
| Model never calls tools | Use `--backend prompted`, or pick a tool-calling model |
| `undecodable frame` | A non-SAPHIR peer on the port; check the transport pairing |
