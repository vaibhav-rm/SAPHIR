# Is SAPHIR novel enough for a paper?

Short answer: **yes, as a systems/protocol paper — not as a cryptography paper.**
The primitives (X25519, HKDF, ChaCha20-Poly1305, CBOR, Bloom filters, ARQ) are
standard. The contribution is the problem framing, the composition under a
brutal byte budget, and the measurement discipline. A reviewer who wants a new
primitive will reject it; a reviewer who wants a new *deployment surface for
agent interoperability* should accept it, provided the evaluation grows beyond
the toy domain.

This note records the prior-art search (Oct–Nov 2026), the claims that survive
it, and the work that would make the paper hard to reject.

## Claim decomposition

| # | Claim | Verdict | Closest prior art | What is actually new |
|---|---|---|---|---|
| 1 | Acoustic rendezvous is a missing transport for agent interoperability | **Novel framing** | MCP/A2A/ACP/ANP, InterSAGE — all assume IP/HTTPS | Naming and scoping the voice-only / PSTN / RF-restricted gap as a protocol problem |
| 2 | A 4-message authenticated pairing fits the acoustic frame budget | **Novel composition** | Acoustic Integrity Codes (WiSec '20), zero-interaction pairing | Agent-level handshake (agent ids, capability advertisement, codec negotiation, resumption) in ≤140 B frames; not physical-layer auth |
| 3 | Structured intents beat English for machine-to-machine calls | **Novel in this channel** | Gibberlink (tones carry English), semantic-alignment work | Ontology-tagged slots + AEAD within 200 B; measured cost model |
| 4 | A human-readable sidecar makes beeps auditable | **Novel** | Enterprise audit logs (HTTPS); nothing for acoustic agents | Per-frame JSONL with decrypted TASK/RESULT summaries, selective disclosure as future work |
| 5 | Local models can adopt the protocol through a harness | **Novel artifact** | Agent tool-calling frameworks (function calling, MCP servers) | First harness that bridges arbitrary local models to an acoustic agent protocol, with allow-lists and audit |

## Prior art, and why each is not the same thing

- **Gibberlink (2025).** The motivating demo. Detection is prompt-level, tones
  carry speech, no auth/negotiation/audit. SAPHIR is the protocol Gibberlink
  lacks. This is the paper's cleanest "gap" citation.
- **ggwave.** A data-over-sound modem (FSK + Reed–Solomon). SAPHIR treats it as
  a byte pipe; the contribution is everything above the modem.
- **Acoustic Integrity Codes (Putz, Álvarez, Classen; ACM WiSec 2020).** The
  most dangerous "already done" citation. AICs authenticate *messages at the
  physical layer* for **short-range device pairing**, using audio hardware as
  an out-of-band channel. It assumes proximate devices, has no session,
  negotiation, structured tasks, agent identities, or audit trail, and its
  threat model is signal cancellation/overshadowing. SAPHIR assumes two agents
  on a call, possibly remote, and builds a session protocol above the modem.
  **Must cite and differentiate explicitly; do not claim "first acoustic
  pairing".**
- **Zero-interaction pairing / secure device pairing literature (2009–2023).**
  Focuses on bootstrapping trust between co-located devices with an out-of-band
  channel. Same physical medium, different problem: no agent semantics, no
  intent exchange, no low-bandwidth task encoding.
- **MCP / A2A / ACP / ANP / InterSAGE.** Standardize tools, task delegation,
  identity, and trust — over HTTP(S). SAPHIR is complementary: a pairing layer
  for the transport they omit. Cite InterSAGE as the natural identity upgrade.
- **Agent protocol security (A2ASecBench, ASB, communication-graph metadata).**
  Imports their attacker methodology (spoof, replay, downgrade) into the
  acoustic setting. SAPHIR's delta is that the cheapest attacks need only a
  speaker, not a network position.
- **Verifiable semantics for agent-to-agent communication (2026).** Motivates
  ontology-tagged intents over free text; SAPHIR is a transport where that
  problem becomes unavoidable because bytes are expensive.
- **STIR/SHAKEN.** Authenticates the *caller's telephone number* at the PSTN
  layer. It says nothing about agent sessions, capabilities, or encrypted
  structured tasks. Good adjacent citation for "telephony has identity, not
  agent rendezvous."

## What reviewers will attack

1. **"This is engineering integration, not research."**
   Mitigation: a formal state-machine spec and a verification artifact
   (ProVerif/Tamarin) for secrecy, authentication, replay, and resumption key
   independence. The protocol is small enough to verify exhaustively — that is
   an advantage, and it converts composition into a result.
2. **"Why sound? Use HTTPS/BLE/QR/ultrasound."**
   Mitigation: state the constraint precisely — the *only* shared channel is a
   voice call, often narrowband and compressed; no pairing UI, no camera, no
   radio. Then measure under Opus/PSTN-like profiles (already modeled; needs
   real trunks).
3. **"No PKI, so the authentication claim is weak."**
   Mitigation: keep the honest framing — *pairing*, not identity. The
   impostor-responder break (`evals/mitm.py`) is already documented. Add
   TOFU + short authentication strings (SAS) as an out-of-band check, and/or a
   DID/PKI mode; evaluate the upgrade path rather than hiding the gap.
4. **"Evaluation is a toy hotel booking."**
   Mitigation: the taxi domain helps but is not enough. Add a second task
   family with different semantics (e.g., appointment scheduling or dispatch
   with constraints) and report task success, not just bytes.
5. **"Numbers are modeled."**
   Mitigation: keep the measured-vs-modeled split (already a strength) and add
   real-room, real-codec measurements. The negative decoder-fragility result is
   a credibility asset, not a weakness.

## The minimum publishable package

A credible submission should include **at least two** of these:

- [ ] Formal verification of the handshake and resumption (ProVerif/Tamarin).
- [ ] Real-room measurements across devices, distances, and codecs (Opus,
      PSTN simulation, speakerphone).
- [ ] An agent-level study: task success and wall-clock time for
      `speech → text → LLM → speech` vs SAPHIR on the same local models.
      **The new harness makes this cheap** — run N models × M tasks and report
      success, turns, bytes, and audit completeness.
- [ ] A security evaluation beyond the three scripted attacks: fuzzing the
      parser (already present), downgrade with a real legacy peer, and
      traffic-analysis limits.

The harness in `docs/HARNESS.md` is the strongest new asset: it turns "we built
a protocol" into "any local model can adopt it, and here is what happens when
they do." That is a measurable, reproducible contribution.

## Venue fit

- **JAAMAS (current target):** plausible if the paper leans on the agent-level
  study and protocol verification. Risk: reviewers may read it as a networking
  artifact. Lead with the agent-interoperability gap, not the modem.
- **AAMAS Blue Sky / extended abstract:** already drafted; safest early
  visibility, low risk.
- **ACM WiSec / MobiSys / IoT-J:** natural for the acoustic + security angle,
  but then AIC and the device-pairing literature become the main comparison
  and the bar for real-room measurement rises.
- **ACM CCS / USENIX Security:** only with formal verification plus a much
  stronger identity story; not the current shape.

## Bottom line

The idea is novel enough to publish **if** it is framed as *the missing
pairing layer for agent interoperability* and backed by either formal
verification or a real measurement study. It is not novel as "cryptography over
sound" and should never be pitched that way. The current draft is an honest,
well-instrumented systems paper; the harness closes the biggest remaining gap —
evidence that heterogeneous local agents can actually use it.

## Citation seeds

- Putz, Álvarez, Classen. *Acoustic Integrity Codes: Secure Device Pairing Using
  Short-Range Acoustic Communication.* ACM WiSec 2020. arXiv:2005.08572.
- Starkov, Pidkuiko. *Gibberlink.* 2025.
- Gerganov. *ggwave.* https://github.com/ggerganov/ggwave
- Anthropic MCP; Google A2A; IBM/Cisco ACP; ANP; InterSAGE (arXiv:2608.13030).
- Ehtesham et al. *A survey of agent interoperability protocols.* 2025.
- Li et al. *A2ASecBench.* ICLR 2026.
- Dangol. *Communication-Graph Metadata.* arXiv:2606.07150.
- *Verifiable Semantics for Agent-to-Agent Communication.* arXiv:2602.16424.
