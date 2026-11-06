---
title: SAPHIR — Secure Acoustic Pairing for AI Agents
hide:
  - navigation
  - toc
---

<div class="hero">
  <div class="hero-copy">
    <p class="eyebrow"><span class="pulse"></span> Research prototype · Protocol v0.1 <span class="eyebrow-extra">· MIT</span></p>
    <h1>AI agents that<br><span class="grad">talk without speaking.</span></h1>
    <p class="lead">
      SAPHIR is the missing pairing layer for voice-only machine encounters.
      Detect the peer, authenticate with ephemeral keys, negotiate capabilities,
      then exchange compact encrypted intents — with an audit trail a human can read.
    </p>
    <div class="cta-row">
      <a href="quickstart/" class="md-button md-button--primary">Get started <span class="arrow">→</span></a>
      <a href="PROTOCOL/" class="md-button">Read the protocol</a>
      <a href="https://github.com/vaibhav-rm/SAPHIR" class="md-button md-button--ghost">GitHub</a>
    </div>
    <p class="hero-note">No IP. No app pairing. No new hardware. Just a shared audio channel.</p>
  </div>
  <div class="hero-terminal">
    <div class="terminal-bar">
      <span class="tdot red"></span><span class="tdot amber"></span><span class="tdot green"></span>
      <span class="terminal-title">saphir · live session</span>
    </div>
    <pre><span class="tok-dim">$</span> saphir pair --peer receptionist
<span class="tok-key">→ HELLO</span>    did:key:z9f2…  need=hotel.book
<span class="tok-key">← WELCOME</span>  sel=saphir-cbor-v1  match=exact
<span class="tok-key">→ KEY1</span>     32B X25519
<span class="tok-key">← KEY2</span>     32B X25519
<span class="tok-ok">✓ ESTABLISHED</span>  hkdf-sha256 → chacha20poly1305

<span class="tok-dim">$</span> saphir task hotel.book
  <span class="tok-warn">▸ [beep 131B]</span>  cbor · aead · seq=3
  <span class="tok-key">←</span> {"ok":true,"confirmation":"HB-2026-1142"}

<span class="tok-dim">$</span> saphir audit --tail 1
  in RESULT 126B  encrypted result → booked</pre>
  </div>
</div>

<div class="metrics">
  <div class="metric"><div class="value">117–139 B</div><div class="label">per encrypted task</div></div>
  <div class="metric"><div class="value">0.22 ms</div><div class="label">full handshake CPU</div></div>
  <div class="metric"><div class="value">95–100%</div><div class="label">delivery under bursty VoIP*</div></div>
  <div class="metric"><div class="value">3 / 3</div><div class="label">scripted attacks blocked</div></div>
</div>
<p class="metric-foot">*with the optional ARQ layer; raw frames score 0% in the same sweep. All figures measured or modeled exactly as stated in <a href="EVALUATION/">Evaluation</a>.</p>

## Why SAPHIR

Voice agents spend two neural speech passes per turn even when both sides are
machines. Gibberlink showed the switch to data-over-sound tones was possible;
SAPHIR makes that switch **safe, negotiable, structured, and inspectable**.

<div class="card-grid">
  <div class="card">
    <span class="card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3z"/><path d="M9 12l2 2 4-4"/></svg></span>
    <h3>Authenticated</h3>
    <p>Ephemeral X25519, HKDF-SHA256, ChaCha20-Poly1305. Forward secrecy per pairing; forged and replayed frames are rejected.</p>
  </div>
  <div class="card">
    <span class="card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/></svg></span>
    <h3>Negotiated</h3>
    <p>Codec and capability advertisement ride inside HELLO/WELCOME. Legacy peers are flagged — never silently downgraded to beeps.</p>
  </div>
  <div class="card">
    <span class="card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9l-6-6z"/><path d="M14 3v6h6"/><path d="M8 13h8M8 17h6"/></svg></span>
    <h3>Auditable</h3>
    <p>Every frame lands in a JSONL sidecar with a human-readable summary and decrypted TASK/RESULT view.</p>
  </div>
  <div class="card">
    <span class="card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12a8 8 0 0 1 16 0"/><path d="M7.5 12a4.5 4.5 0 0 1 9 0"/><circle cx="12" cy="12" r="1.6"/></svg></span>
    <h3>Transport-agnostic</h3>
    <p>Any ordered byte pipe works: audible FSK, PSTN, loopback, a shared directory, or TCP. The acoustic path is one adapter.</p>
  </div>
  <div class="card">
    <span class="card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3v5M15 3v5"/><path d="M6 8h12v3a6 6 0 0 1-12 0V8z"/><path d="M12 17v4"/></svg></span>
    <h3>Adoptable</h3>
    <p>A harness exposes six tools to any local model — Ollama, llama.cpp, LM Studio, vLLM, or prompt-only completion.</p>
  </div>
  <div class="card">
    <span class="card-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/></svg></span>
    <h3>Honest</h3>
    <p>Measured and modeled numbers are separated. The PKI gap, replay limits, and missing real-room data are documented, not hidden.</p>
  </div>
</div>

## The exchange

<div class="seq" role="img" aria-label="SAPHIR sequence: English opening, HELLO, WELCOME, KEY1, KEY2, then encrypted TASK and RESULT frames between caller and receptionist.">
  <div class="seq-lifelines" aria-hidden="true"></div>
  <div class="seq-head"><span>Caller (AI)</span><span>Receptionist (AI)</span></div>
  <div class="seq-note">English opening — Act 1, the wasteful STT → LLM → TTS loop</div>
  <div class="seq-row to-right"><span class="seq-label">HELLO <em>did · codecs · need</em></span></div>
  <div class="seq-row to-left"><span class="seq-label">WELCOME <em>selected codec · capability verdict</em></span></div>
  <div class="seq-row to-right"><span class="seq-label">KEY1 <em>32B X25519 ephemeral</em></span></div>
  <div class="seq-row to-left"><span class="seq-label">KEY2 <em>32B X25519 ephemeral</em></span></div>
  <div class="seq-note accent">HKDF-SHA256 → 32B ChaCha20-Poly1305 session key</div>
  <div class="seq-row to-right"><span class="seq-label">TASK <em>encrypted CBOR intent + slots</em></span></div>
  <div class="seq-row to-left"><span class="seq-label">RESULT <em>encrypted CBOR result</em></span></div>
  <div class="seq-note">Every frame mirrored to the JSONL sidecar</div>
</div>

Every frame stays inside one ggwave audible transmission. The handshake is
optional on return visits: a ticket resumes pairing in two frames instead of
four.

## Start in 60 seconds

=== "Web demo"

    Two agents, real ggwave tones, real crypto, real attack buttons:

    ```bash
    cd demo/web
    python3 -m http.server 8080
    # open http://localhost:8080/?role=caller
    # and  http://localhost:8080/?role=receptionist
    ```

    Needs microphone permission and localhost/HTTPS. Headless check:
    `node demo/web/smoke-test.mjs`.

=== "CLI"

    The same three acts in a terminal, no audio hardware required:

    ```bash
    pip install -r requirements.txt
    PYTHONPATH=src python demo/demo_cli.py
    ```

=== "Local AI"

    Attach SAPHIR to any local model through six tools:

    ```bash
    PYTHONPATH=src python -m saphir.harness demo

    # service side
    PYTHONPATH=src python -m saphir.harness serve --agent hotel-bot \
      --offers hotel.check,hotel.book --handler hotel --listen 127.0.0.1:9001

    # model side
    PYTHONPATH=src python -m saphir.harness agent --agent caller-ai \
      --need hotel.book --goal "Book a double room for 2026-11-02" \
      --backend ollama --model qwen2.5:1.5b --connect 127.0.0.1:9001
    ```

=== "Tests"

    ```bash
    PYTHONPATH=src python -m pytest tests/ -q
    PYTHONPATH=src python evals/attacks.py
    PYTHONPATH=src python evals/bench.py
    ```

## Explore the docs

<div class="docs-grid">
  <a class="doc-card" href="quickstart/">
    <span class="doc-kicker">Get started</span>
    <h3>Quickstart</h3>
    <p>Install, run the demo, pair two agents, verify the audit log.</p>
  </a>
  <a class="doc-card" href="PROTOCOL/">
    <span class="doc-kicker">Protocol</span>
    <h3>Wire format</h3>
    <p>Frame layout, message types, measured sizes, and the 200-byte cap.</p>
  </a>
  <a class="doc-card" href="EVALUATION/">
    <span class="doc-kicker">Security</span>
    <h3>Evaluation &amp; threat model</h3>
    <p>Attack matrix, robustness sweeps, cost model, and what is still open.</p>
  </a>
  <a class="doc-card" href="HARNESS/">
    <span class="doc-kicker">Integration</span>
    <h3>Local-AI harness</h3>
    <p>Six tools, three transports, four model backends, and guardrails.</p>
  </a>
  <a class="doc-card" href="NOVELTY/">
    <span class="doc-kicker">Research</span>
    <h3>Novelty &amp; prior art</h3>
    <p>What is new, what is standard, and what a reviewer will attack.</p>
  </a>
  <a class="doc-card" href="FAQ/">
    <span class="doc-kicker">Project</span>
    <h3>FAQ</h3>
    <p>Why not MCP/A2A, is it secure, does it work on phones, what is missing.</p>
  </a>
</div>

!!! warning "Research prototype"
    SAPHIR v0.1 is not audited for production use. It has no PKI-backed
    identity, no group sessions, and no real-room acoustic measurements yet.
    The impostor-responder break is demonstrated on purpose in `evals/mitm.py`.
    Read [Identity](IDENTITY.md) and [Status & roadmap](STATUS.md) before
    deploying anything.

<div class="cite-card">
  <div>
    <p class="doc-kicker">If you use this work</p>
    <p class="cite-title">Rathod, V. <em>SAPHIR: Secure Acoustic Pairing for Heterogeneous Inter-agent Rendezvous.</em> 2026.</p>
    <p class="cite-note">Citation metadata in <a href="https://github.com/vaibhav-rm/SAPHIR/blob/main/CITATION.cff">CITATION.cff</a> · MIT license.</p>
  </div>
  <a class="md-button md-button--primary" href="https://github.com/vaibhav-rm/SAPHIR">View on GitHub</a>
</div>
