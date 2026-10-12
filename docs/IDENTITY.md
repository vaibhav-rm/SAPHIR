# Identity & deployment guidance

## Two identity modes

| | Ephemeral (default) | Stable (deployment) |
|---|---|---|
| DID | `did:key:z` + random per session | operator-assigned, long-lived |
| Pairing | always full handshake | full once, then resumption tickets |
| Peer recognition | none (strangers every time) | TOFU: TicketStore remembers peer DIDs |
| Use for | demos, first contact, untrusted encounters | fleets, recurring partners |

Pass `did=` explicitly to opt into stable identity:
`SaphirSession("receptionist", did="did:key:zhotel-01", store=my_store)`.
Ephemeral is the safe default: rotating DIDs leak nothing across pairings.

## What stable identity does and does NOT give you

- Gives: cheaper return visits (resumption, §12), peer continuity (the same
  DID across sessions), no-equivocation within a pairing (DID is checked
  against the handshake transcript by participants that log it).
- Does NOT give: first-contact authentication. A stable-looking DID string is
  self-asserted — our `evals/mitm.py` demonstrates the break. Real
  authentication needs PKI-bound DIDs (verifiable credentials where IP
  exists), which is tracked as the top future item in `docs/publication-plan.md`.

## Production checklist (all open)

- [ ] PKI-bound identity + credential verification in HELLO/WELCOME
- [ ] MLS-style group sessions (currently two-party only)
- [ ] Ultrasound profiles characterized per hardware (currently audible only)
- [ ] Real room measurements (currently byte-level models + in-process ggwave)
- [ ] Schema-driven capability dictionaries (currently hand dictionaries)
- [ ] Sidecar selective disclosure (currently full plaintext logs)
- [ ] Security audit of this codebase (research prototype, unaudited)
