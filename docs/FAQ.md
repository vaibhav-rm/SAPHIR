# FAQ

The questions that come up before the technical docs.

## Why not just use MCP, A2A, or HTTPS?

Those protocols assume IP connectivity, URL-addressable agents, and a working
TLS stack. SAPHIR targets the encounters they cannot reach: a voice-only call,
a PSTN trunk, an offline or RF-restricted room, or two agents that share
nothing but a speaker and a microphone. It is complementary — an acoustic
pairing layer beneath the existing agent stack, not a replacement for it.

## Isn't this just Gibberlink?

Gibberlink demonstrated the important observation: two AI agents on a call can
detect each other and switch from speech to data-over-sound tones. It is a demo,
not a protocol — the switch is prompt-level, the tones carry English, and there
is no authentication, negotiation, structure, or audit trail. SAPHIR keeps the
observation and supplies the missing layer.

## What does "secure" mean here?

Within the MVP scope:

- **Confidentiality and integrity** for TASK/RESULT frames (ChaCha20-Poly1305,
  sender-bound AAD).
- **Forward secrecy** per pairing; ephemeral keys are discarded.
- **Replay rejection** via sequence and nonce/ciphertext sets.
- **Downgrade flagging**: a peer that cannot speak the structured codec never
  silently receives beeps.

What it does **not** provide yet: authenticated identity. An impostor responder
can run its own handshake and read tasks. That break is demonstrated in
`evals/mitm.py`; the fix is PKI-backed DIDs or a TOFU + short authentication
string (SAS) flow. Do not deploy SAPHIR as an identity system today.

## Does it work on a real phone call?

The protocol is designed for it, but the current evidence is a byte-level model
and a two-device browser demo. Real PSTN/Opus transcoding, speakerphone audio,
and room acoustics are explicit future work. The honest claim is: the framing
and budget are built for narrowband audio; over-air validation across carriers
is not done.

## How can 100–200 bytes be enough?

Because the wire carries *intents and slots*, not sentences:

```text
ChaCha20Poly1305(cbor({i: "hb", s: {d: "261102", r: "dbl", n: 2}, ts: ...}))
```

The encoder uses short keys and dictionary values, and the whole envelope is
capped at 200 bytes. That fits a single ggwave audible transmission. The win is
not raw byte count versus English text — it is eliminating two neural speech
passes per turn. The evaluation states this explicitly.

## Does it need special hardware?

No. The core library and harness run on any Python 3.11+ machine with no audio
hardware at all. The over-air demo needs a speaker and microphone. The protocol
is transport-agnostic: loopback, files, TCP, and audible FSK are all adapters.

## Can any local model use it?

Yes. The harness exposes six tools (`saphir_status`, `saphir_pair`,
`saphir_send_task`, `saphir_serve`, `saphir_audit`, `saphir_close`) and ships
backends for:

- Ollama native tool calling
- OpenAI-compatible servers (llama.cpp, LM Studio, vLLM, LocalAI)
- Prompt-only models via a JSON tool convention
- Scripted/deterministic backends for tests

The model never handles keys or raw frames; it sees JSON tool results.
See [Local-AI harness](HARNESS.md).

## Why is the audit sidecar a big deal?

Because opaque beeps are an operational and safety problem. Every frame is
appended to JSONL with direction, type, size, and a decrypted summary. An
operator can answer "what did these two agents agree to?" without instrumenting
the crypto. Selective disclosure for sensitive fields is future work.

## How fast is it?

Measured CPU cost on the development machine: a full four-message handshake is
about **0.22 ms**; sealing or opening one task is tens of microseconds. Airtime
dominates. At the modeled 32 Bps audible goodput, tasks take seconds — SAPHIR
trades wall-clock time for near-zero neural compute. See
[Evaluation](EVALUATION.md) for the full accounting.

## What is the biggest weakness?

Identity. The protocol authenticates *the session*, not *the peer's name*. The
second biggest is evidence: no real-room measurements yet. Both are stated in
the repository rather than buried.

## Can I use it in production?

No. It is a research prototype, not audited, with no PKI and no group support.
Use it for research, demos, and red-teaming. The MIT license permits reuse, but
the security claims are scoped to what is written in
[Evaluation](EVALUATION.md).

## How do I report a problem?

Open an issue at
[github.com/vaibhav-rm/SAPHIR/issues](https://github.com/vaibhav-rm/SAPHIR/issues).
Security-relevant reports are especially welcome; the protocol is public so it
can be red-teamed.
