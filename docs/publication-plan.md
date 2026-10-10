# Publication plan (decided Oct 2026)

Author: Rathod Vaibhav Vishwas Ram, CSE, R. V. College of Engineering, Bengaluru.
Constraint: **no conference travel.** So the path is journal + preprint, not venues.

## Decision
1. **Primary: JAAMAS** (Journal of Autonomous Agents and Multiagent Systems, Springer).
   Exact community for agent pairing work; no publication fee; archival.
   Slow review (months) — submit the full version when reliability + over-air/sim evals land.
2. **Immediate: arXiv** (cs.MA / cs.CR). Establishes priority now; required for visibility
   while the journal reviews. Post the full-length manuscript, not the Blue Sky sketch.
3. **Backup: IEEE Access.** Fast (~4–6 weeks) but APC ≈ $1,950 — only if speed beats budget.
4. **Not pursuing:** AAAI/AAMAS/IJCAI/ICLR main + workshops (all expect in-person presentation).
   The Blue Sky draft in `paper/bluesky/` stays as a working sketch that feeds the journal
   manuscript's vision section.

## What the journal manuscript still needs (vs this repo today)
- [x] Protocol + threat model + prototype
- [x] Attack matrix (replay/forgery/downgrade)
- [x] Raw-channel robustness sweep
- [x] Reliability framing (ACK/retry) + re-sweep showing the cliff fixed (`ReliableLink`, §5)
- [x] Amortization curve (handshake cost vs dialogue length; §6 + figure)
- [x] Channel-profile simulation (burst models + sweep; §7 — waveform/over-air still future)
- [x] Expanded related work (full survey table, not just the Blue Sky paragraph)
- [x] Reproducibility appendix (commands, seeds, artifact link)
