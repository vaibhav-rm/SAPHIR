# SAPHIR web demo

The visible demo: two AI agents on a call, English first, then authenticated tone bursts.

## Run it

```bash
cd demo/web
python3 -m http.server 8080
# open http://localhost:8080
```

(No build step, no dependencies. `file://` also works, but a local server is
more reliable for AudioContext autoplay policies. Click anywhere once if the
browser blocks audio before first interaction.)

## What to click

1. **▶ Run full demo** — Act 1 (spoken English via browser TTS) → Act 2
   (HELLO/WELCOME/KEY beeps + TASK/RESULT beeps with live spectrogram) →
   attack buttons unlock.
2. **⚔ Replay last TASK** — replays the captured tones; the receiver's real
   replay check rejects them (`seq reused`). Watch the audit panel.
3. **⚔ Forge TASK** — flips a byte; rejected as an auth failure.
4. **silent** checkbox — skips audio for fast/volume-off runs.

## What's real vs simulated (stated in the page footer too)

- **Real:** every tone burst FSK-encodes that frame's actual bytes
  (preamble + length + payload, mark/space tones); the receiver's
  replay/auth decisions run real check logic mirroring `src/saphir/`.
- **Simulated:** acoustic capture/decode (bytes pass through reliably) and the
  key exchange display. Audited X25519/ChaCha lives in `src/saphir/crypto.py`;
  the demo page is JSON-framed while the wire protocol uses CBOR.
