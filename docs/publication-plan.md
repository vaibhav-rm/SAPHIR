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
- [x] Capability discovery preliminary (bloom + verdicts; §11 — schema-driven open vocabularies still future)
- [x] Impostor-responder demo pinning the PKI gap (§10)
- [x] Session resumption with tickets + expiry (§12)
- [x] Decoder characterization (single-shot fragility documented; §9 — real rooms still future)
- [x] Expanded related work (full survey table, not just the Blue Sky paragraph)
- [x] Reproducibility appendix (commands, seeds, artifact link)

## Submission mechanics (for the author, when ready)

- Format: Springer Nature LaTeX template (`sn-jnl`, `pdflatex,sn-basic,referee`
  options). Easiest path: paste `paper/journal/main.tex` body into the
  Overleaf SN template (30–60 min); the class file could not be vendored here,
  and Editorial Manager validates on upload anyway. Keep `thebibliography` or
  convert to a `.bib` — both accepted with `sn-basic`.
- Required Declarations block (Springer standard, draft text ready to paste):
  - Funding: no funding was received for this work.
  - Competing interests: the author declares no competing interests.
  - Data availability: code, harnesses, and demo at
    https://github.com/vaibhav-rm/SAPHIR; every number reproduces from
    `docs/REPRODUCIBILITY.md`.
  - Author contributions: single-author work.
  - Ethics approval: not applicable (no human subjects, no personal data).
- License: repo is MIT (`LICENSE`); artifact runs without accounts, keys, or hardware.
- Cite-as: `CITATION.cff` at repo root (GitHub renders it automatically).
