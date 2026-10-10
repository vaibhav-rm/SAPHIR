# Paper skeleton — one outline, three targets

Grow the same document: Blue Sky (short, vision) → IJCAI (full, evals) → journal (extended).

## Blue Sky Ideas (AAMAS 2027, due Nov 12 2026) — ~4 pages
1. **Intro (0.5p):** voice agents talking to voice agents; Gibberlink went viral, but beeps without trust.
2. **Vision (1p):** any two agents on a bare audio channel should pair like Bluetooth:
   detect → negotiate → encrypt → collaborate → stay auditable. Name the 5 properties.
3. **Why HTTP protocols don't solve it (0.75p):** MCP/A2A/InterSAGE assume IP;
   table of channels they leave uncovered (PSTN, offline rooms, noisy speakers).
4. **SAPHIR sketch (1p):** handshake diagram + threat model (spoof/replay/downgrade table).
5. **Preliminary evidence (0.5p):** handshake works, attacks blocked (this repo's numbers).
6. **Open challenges (0.5p):** reliability framing, sub-140B compaction, DID PKI, traffic analysis.
   End with 3 concrete research questions for the community.

## IJCAI 2027 (due Jan 11 2027) — 7-8 pages: Blue Sky + the following
7. **Full protocol spec (1.5p):** wire format, CBOR schema, crypto (X25519/HKDF/ChaCha), state machine.
8. **Evaluation (2p):** bench table (bytes/time/cost) + robustness sweep table
   (`evals/robustness.py`) + attack matrix (`evals/attacks.py`).
9. **Related work (1p):** position vs Gibberlink, MCP/A2A/ANP survey, InterSAGE, A2ASecBench, ASB.
10. **Ablations:** full-form vs compact encoding sizes; handshake amortization over N turns.

## Journal (JAAMAS / IEEE Access, rolling) — IJCAI + the following
11. Real over-air measurements (two laptops/phones, room noise levels, Opus/G.711).
12. Formal handshake verification sketch (replay/downgrade lemmas).
13. Multi-turn amortization curve + failure-mode analysis from the sweep.
14. Artifact appendix: repo link, repro commands, demo video.

## Writing order (do this, in this order)
1. Threat-model table + handshake figure (reused in all three versions).
2. Evaluation tables (bench + robustness + attacks) — numbers first, prose second.
3. Related-work paragraph per cited paper (one claim each: what they assume, what they miss).
4. Vision/open-challenges — easiest once 1–3 exist.
