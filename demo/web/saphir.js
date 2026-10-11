/* SAPHIR web demo core: demo framing, FSK modem, session logic, audit.
 * - Tones REALLY encode each frame's bytes (FSK mark/space + preamble + len).
 * - Capture/decode is simulated (we pass the bytes through); the receiver's
 *   replay/auth checks are REAL logic (seq sets), mirroring src/saphir/.
 * - Crypto here is illustrative; audited crypto lives in src/saphir/crypto.py.
 */
"use strict";

const F_MARK = 2093.66;   // C7
const F_SPACE = 1567.98;  // G6
const BIT_MS = 8;
const PREAMBLE = [0xAA, 0xAA];

let _seq = 0;
const rnd = (n) => Array.from(crypto.getRandomValues(new Uint8Array(n)))
  .map((b) => b.toString(16).padStart(2, "0")).join("");

function buildFrame(type, sender, payload) {
  return { v: 1, type, seq: _seq++, sender, nonce: rnd(8), payload };
}
const frameBytes = (f) => new TextEncoder().encode(JSON.stringify(f));
const hexPreview = (bytes, n = 24) =>
  Array.from(bytes.slice(0, n)).map((b) => b.toString(16).padStart(2, "0")).join(" ") +
  (bytes.length > n ? " …" : "");

/* ---------------- FSK modem (WebAudio) ---------------- */
let actx = null, analyser = null, waveAnalyser = null;
function audio() {
  if (!actx) {
    actx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = actx.createAnalyser(); analyser.fftSize = 2048; analyser.smoothingTimeConstant = 0.8;
    waveAnalyser = actx.createAnalyser(); waveAnalyser.fftSize = 1024;
    const master = actx.createGain(); master.gain.value = 0.5;
    master.connect(analyser); analyser.connect(waveAnalyser); waveAnalyser.connect(actx.destination);
    audio.master = master;
  }
  if (actx.state === "suspended") actx.resume();
  return actx;
}

function bitsOf(bytes) {
  const len = bytes.length;
  const all = new Uint8Array([...PREAMBLE, (len >> 8) & 0xff, len & 0xff, ...bytes]);
  const bits = [];
  for (const b of all) for (let i = 0; i < 8; i++) bits.push((b >> i) & 1);
  return bits;
}

// Plays the frame's actual bytes as FSK tones. Resolves with {aborted}.
// onBit(i, total) is called as each bit starts (for progress + announce).
function playFrame(bytes, onBit) {
  const silent = document.getElementById("chkSilent").checked;
  const bits = bitsOf(bytes);
  if (silent) { onBit(bits.length, bits.length); return Promise.resolve({ aborted: false }); }
  audio();
  const t0 = actx.currentTime + 0.05;
  const osc = actx.createOscillator(); osc.type = "sine";
  const g = actx.createGain(); g.gain.value = 0;
  osc.connect(g); g.connect(audio.master); osc.start(t0);
  const bit = BIT_MS / 1000;
  bits.forEach((b, i) => {
    const t = t0 + i * bit;
    osc.frequency.setValueAtTime(b ? F_MARK : F_SPACE, t);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(0.9, t + 0.002);
    g.gain.setValueAtTime(0.9, t + bit - 0.002);
    g.gain.exponentialRampToValueAtTime(0.0001, t + bit);
  });
  osc.stop(t0 + bits.length * bit + 0.05);
  return new Promise((resolve) => {
    let i = 0; playFrame._abort = false;
    const timer = setInterval(() => {
      if (playFrame._abort) {
        clearInterval(timer);
        try { osc.stop(); } catch (_) {}
        resolve({ aborted: true }); return;
      }
      i += 4; onBit(Math.min(i, bits.length), bits.length);
      if (i >= bits.length) { clearInterval(timer); resolve({ aborted: false }); }
    }, BIT_MS * 4);
  });
}
function abortAudio() { playFrame._abort = true; }

/* ---------------- Session logic (real replay/auth checks) ---------------- */
class DemoSession {
  constructor(id) {
    this.id = id;
    this.established = false;
    this.seenSeq = new Set();
    this.fakeKey = rnd(16);
    this.taskSeq = 0;
  }
  // Receiver-side check, mirrors session.open_task replay protection.
  accept(frame) {
    const key = frame.sender + ":" + frame.seq;
    if (this.seenSeq.has(key)) return { ok: false, reason: `replay: seq ${frame.seq} reused` };
    if (frame.tampered) return { ok: false, reason: "auth tag mismatch (InvalidTag)" };
    this.seenSeq.add(key);
    return { ok: true };
  }
}

/* ---------------- Audit + metrics ---------------- */
const Audit = {
  frames: 0, bytes: 0, blocked: 0,
  add(dir, type, sender, nbytes, summary, cls = "") {
    this.frames++; this.bytes += nbytes;
    const li = document.createElement("li");
    if (cls) li.className = cls;
    li.innerHTML = `<b>[${dir}] ${type}</b> ${sender} · ${nbytes}B<br>${summary}`;
    document.getElementById("audit").prepend(li);
    document.getElementById("mFrames").textContent = this.frames;
    document.getElementById("mBytes").textContent = this.bytes;
  },
  blockedAttack(reason) {
    this.blocked++;
    document.getElementById("mBlocked").textContent = this.blocked;
    this.add("ATTACK", "BLOCKED", "receiver", 0, reason, "bad");
  },
  reset() {
    this.frames = this.bytes = this.blocked = 0;
    document.getElementById("audit").innerHTML = "";
    for (const id of ["mFrames", "mBytes", "mBlocked"])
      document.getElementById(id).textContent = "0";
  },
};

/* ---------------- Spectrogram + waveform ---------------- */
function startScopes() {
  const s = document.getElementById("spectro"), w = document.getElementById("wave");
  const sctx = s.getContext("2d"), wctx = w.getContext("2d");
  sctx.fillStyle = "#05070f"; sctx.fillRect(0, 0, s.width, s.height);
  const freq = new Uint8Array(1024), time = new Uint8Array(1024);
  const color = (v) => `rgb(${Math.min(255, v * 2)},${Math.floor(v * 0.9)},${Math.floor(255 - v)})`;
  (function loop() {
    requestAnimationFrame(loop);
    if (!analyser) return;
    analyser.getByteFrequencyData(freq);
    const img = sctx.getImageData(1, 0, s.width - 1, s.height);
    sctx.putImageData(img, 0, 0);
    const x = s.width - 1;
    for (let y = 0; y < s.height; y++) {
      const bin = Math.floor((y / s.height) * 300) + 20;
      sctx.fillStyle = color(freq[bin] || 0);
      sctx.fillRect(x, s.height - 1 - y, 1, 1);
    }
    waveAnalyser.getByteTimeDomainData(time);
    wctx.fillStyle = "#05070f"; wctx.fillRect(0, 0, w.width, w.height);
    wctx.strokeStyle = "#35d07f"; wctx.beginPath();
    time.forEach((v, i) => {
      const px = (i / time.length) * w.width, py = (v / 255) * w.height;
      i ? wctx.lineTo(px, py) : wctx.moveTo(px, py);
    });
    wctx.stroke();
  })();
}
