# Status & roadmap

SAPHIR is a research prototype at **protocol v0.1**. It is functional end to
end and every claim below is reproducible from this repository. It is not
audited, not standardized, and not ready for production deployment.

## Where the project stands

| Area | State | Evidence |
|---|---|---|
| Wire protocol | Complete v0.1 | [Wire format](PROTOCOL.md) |
| Handshake + AEAD messaging | Complete | `src/saphir/session.py`, 60 tests |
| Capability discovery | Complete (registry + bloom) | `src/saphir/caps.py`, `tests/test_caps.py` |
| Session resumption | Complete, ticket-based | `src/saphir/resume.py`, `tests/test_resume.py` |
| Admission guard | Complete (freshness + rate limit) | `src/saphir/guard.py` |
| Reliability (ARQ) | Complete | `src/saphir/channel.py`, `evals/reliability.py` |
| Over-air ggwave path | Complete demo | `demo/web/` |
| Local-AI harness | Complete | [Harness](HARNESS.md), 18 tests |
| Evaluation harnesses | Complete (9) | [Evaluation](EVALUATION.md) |
| Real-room measurements | **Open** | needs hardware and time |
| PKI-backed identity | **Open** | break demonstrated in `evals/mitm.py` |
| Group sessions (MLS) | **Open** | design work |
| Schema-driven capability dictionaries | **Open** | research question |
| Third-party security audit | **Open** | external |

## Completed milestones

- [x] Baseline: ggwave framing, booking task, cost model
- [x] Handshake, crypto, audit sidecar, CLI demo
- [x] Browser demo with real ggwave, lossy-channel sweeps, burst profiles
- [x] Compact task encoding: every frame, including handshake, fits one transmission
- [x] Capability discovery in HELLO with fast decline
- [x] Session resumption with tickets, expiry, and implicit verification
- [x] Admission guard: HELLO freshness window and per-sender rate limiting
- [x] Negative result documented: single-shot decoder fragility
- [x] Impostor-responder break documented to pin the PKI gap
- [x] CPU cost profiling (handshake 0.22 ms; seal/open tens of microseconds)
- [x] Local-AI harness for Ollama, OpenAI-compatible, and prompt-only models

## Open work, honestly stated

These are not backlog items that a weekend closes. They need hardware, new
research, or an author action:

1. **Real-room acoustics.** Distance, speaker/mic quality, reverberation,
   Opus/PSTN transcoding. The current sweeps are byte-level models.
2. **Identity.** Ephemeral DIDs are pairing handles, not identity. The
   impostor-responder attack succeeds against the current design; fixing it
   needs PKI or a TOFU + short-authentication-string flow.
3. **Groups.** v0.1 is two-party. MLS-style group keys are future work.
4. **Scalable ontologies.** Intent dictionaries are demo-scale; schema-driven
   negotiation is a research question, not an implementation detail.
5. **Selective disclosure.** The sidecar is all-or-nothing today; metadata
   leakage is a known concern.
6. **External audit.** No third party has reviewed the protocol or code.

## Compatibility

| Component | Version / requirement |
|---|---|
| Protocol | v0.1 (envelope `v: 1`) |
| Python | 3.11+ |
| Core deps | `cbor2`, `cryptography` |
| Optional | `ggwave` (real acoustic codec) |
| Harness backends | Ollama, OpenAI-compatible, prompted JSON |
| License | MIT |
