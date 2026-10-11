# SAPHIR web demo — real ggwave, real crypto, real attacks

Two AI agents on a call, English first, then authenticated tone bursts.
Open this page on **two devices** (phones/laptops), pick one role each —
or run both roles on one device (speaker → mic loopback).

## Run it

```bash
cd demo/web
python3 -m http.server 8080
# open http://localhost:8080/?role=caller   (device 1)
# open http://localhost:8080/?role=receptionist   (device 2)
# ...or ?role=both on a single device. No role = role picker.
```

Requires microphone permission + a secure context (localhost counts as secure;
LAN/devices need HTTPS). Allow the mic, press **Start** on both sides.

## What is real

- **Transport:** vendored official ggwave WASM (`vendor/ggwave.js`, MIT) —
  every frame is really FSK-modulated and really decoded from the mic
  (audible-**fastest** profile, ≤138B frames, Reed-Solomon on the wire, TX gain
  dialed to 0.35 for ears). Fastest halves airtime vs fast (≈17s not ≈31s on
  big frames) and retry absorbs the robustness cost. Ultrasound was rejected:
  laptop speakers/mics roll off where it lives, so it would break the demo.
- **Crypto:** ECDH P-256 key exchange + AES-GCM tasks with fresh random IVs,
  via WebCrypto. Replay sets mirror `src/saphir/`.
- **Reliability:** response-driven retransmission — each reply doubles as the
  ACK (HELLO→WELCOME→KEY1→KEY2→TASK→RESULT→DONE), up to 3 tries. Retries
  re-seal with fresh IVs: ggwave has content-dependent first-try misses, so
  retransmitting identical bytes would replay a poison payload forever.
- **Attacks:** ⚔ Replay re-transmits captured tones (rejected by seq sets);
  ⚔ Forge flips a ciphertext byte with a fresh seq (rejected by AES-GCM).
- English lines are spoken with browser TTS.

## Headless test (no mic needed)

```bash
node demo/web/smoke-test.mjs
```

Drives both sessions through loopback delivery with real crypto, one injected
TASK loss (retry must save it), then all four attacks. Must print SMOKE OK.

## What's still demo-grade

JSON framing (wire protocol uses CBOR), illustrative DIDs, two-party only.
Audited protocol code: `src/saphir/`. Frame shapes are regression-guarded by
`evals/ggwave_frames.py` against the real Python ggwave build.
