/* Real ggwave TX/RX link. API mirrors the official ggwave-js example:
 * ggwave_factory() -> getDefaultParameters -> init -> encode/decode.
 * TX pauses capture during transmission (official pattern).
 */
"use strict";

const GG = {
  ready: false, gg: null, inst: null, ctx: null,
  protocol: null, capturing: false, recorder: null, mediaStream: null,
  onText: null, // (text) => void, called for every decoded payload
  log: (...a) => console.log("[ggwave]", ...a),

  async init(ctx) {
    if (this.ready) return;
    this.ctx = ctx;
    const gg = await ggwave_factory();
    gg.disableLog();
    const params = gg.getDefaultParameters();
    params.sampleRateInp = ctx.sampleRate;
    params.sampleRateOut = ctx.sampleRate;
    this.inst = gg.init(params);
    this.gg = gg;
    // FASTEST: ~2x shorter airtime than FAST (31s -> 17s on big frames) and a
    // higher ceiling. Retry absorbs the robustness cost. Volume stays easy.
    this.protocol = gg.ProtocolId.GGWAVE_PROTOCOL_AUDIBLE_FASTEST;
    // TX bus with a tap for the wave canvas; mic gets its own tap (no feedback).
    this.txBus = ctx.createGain(); this.txBus.gain.value = 0.35; // comfortable, still decodable
    this.txAn = ctx.createAnalyser(); this.txAn.fftSize = 2048;
    this.txBus.connect(this.txAn); this.txBus.connect(ctx.destination);
    this.micAn = ctx.createAnalyser(); this.micAn.fftSize = 2048;
    this._txUntil = 0; this._txColor = "#4ade80";
    this._peerUntil = 0; this._peerColor = "#4ade80";
    this.ready = true;
  },

  // Heard a decoded frame from peer f ('c' | 'r'): flash the wave in their color.
  flashPeer(f) {
    this._peerColor = f === "r" ? "#e0a030" : "#4ade80";
    this._peerUntil = performance.now() + 1500;
  },

  // Encode text -> real ggwave waveform -> play. Returns airtime ms.
  async send(text, color) {
    if (!this.ready) throw new Error("ggwave not initialized (click Start first)");
    if (text.length > 138) throw new Error(`payload ${text.length}B exceeds 138B ggwave budget`);
    this.setCapture(false);
    const wav = this.gg.encode(this.inst, text, this.protocol, 10);
    const buf = this.ctx.createBuffer(1, wav.length, this.ctx.sampleRate);
    buf.getChannelData(0).set(wav);
    const src = this.ctx.createBufferSource();
    src.buffer = buf; src.connect(this.txBus);
    const ms = (wav.length / this.ctx.sampleRate) * 1000;
    if (color) this._txColor = color;
    this._txUntil = performance.now() + ms;
    src.start();
    await new Promise((r) => { src.onended = r; setTimeout(r, ms + 400); });
    await new Promise((r) => setTimeout(r, 250)); // tail guard
    return ms;
  },

  setCapture(on) {
    if (on === this.capturing) return;
    this.capturing = on;
    const dot = document.getElementById("micdot"), lab = document.getElementById("miclabel");
    if (dot) dot.className = "mdot " + (on ? "on" : "");
    if (lab) lab.textContent = on ? "mic live" : "mic off";
    if (this.recorder) {
      try {
        if (on) { this.mediaStream.connect(this.recorder); this.recorder.connect(this.silence); }
        else { this.mediaStream.disconnect(this.recorder); this.recorder.disconnect(this.silence); }
      } catch (_) {}
    }
  },

  async startMic() {
    const constraints = { audio: { echoCancellation: false, autoGainControl: false, noiseSuppression: false } };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    this.mediaStream = this.ctx.createMediaStreamSource(stream);
    this.mediaStream.connect(this.micAn); // tap only — never routed to speakers
    this.silence = this.ctx.createGain(); this.silence.gain.value = 0;
    this.silence.connect(this.ctx.destination); // ScriptProcessor needs a sink; muted
    const Rec = this.ctx.createScriptProcessor ? "createScriptProcessor" : "createJavaScriptNode";
    this.recorder = this.ctx[Rec](1024, 1, 1);
    const gg = this.gg, inst = this.inst, self = this;
    this.recorder.onaudioprocess = (e) => {
      if (!self.capturing) return;
      const ch = new Float32Array(e.inputBuffer.getChannelData(0));
      const res = gg.decode(inst, new Int8Array(ch.buffer));
      if (res && res.length > 0) {
        try {
          const text = new TextDecoder("utf-8").decode(res);
          if (self.onText) self.onText(text);
        } catch (_) {}
      }
    };
    this.setCapture(true); // mic live; onaudioprocess now fires
  },

  // Mic self-test: play a short probe and listen for our own decode.
  // Returns true if this device can hear itself (loopback path works).
  async probe() {
    const stamp = Math.random().toString(16).slice(2, 6);
    const text = JSON.stringify({ t: "PROBE", q: stamp });
    return new Promise(async (resolve) => {
      this._probe = { text, resolve };
      try { await this.send(text); } catch (_) { this._probe = null; resolve(false); return; }
      this.setCapture(true);
      setTimeout(() => {
        if (this._probe) { this._probe = null; resolve(false); }
      }, 12000);
    });
  },
  probeEat(text) {
    if (this._probe && text === this._probe.text) {
      const r = this._probe.resolve; this._probe = null; r(true); return true;
    }
    return false;
  },
  scope(canvas) {
    const g = canvas.getContext("2d");
    const mic = new Uint8Array(2048), tx = new Uint8Array(2048);
    const W = canvas.width, H = canvas.height;
    const draw = () => {
      requestAnimationFrame(draw);
      g.fillStyle = "#000"; g.fillRect(0, 0, W, H);
      g.strokeStyle = "#1c1c1c";
      g.beginPath(); g.moveTo(0, H / 2); g.lineTo(W, H / 2); g.stroke();
      if (this.micAn) {
        this.micAn.getByteTimeDomainData(mic);
        const peerLive = performance.now() < this._peerUntil;
        g.strokeStyle = peerLive ? this._peerColor : "#3d3d3d"; g.lineWidth = peerLive ? 1.5 : 1;
        g.beginPath();
        mic.forEach((v, i) => {
          const x = (i / mic.length) * W, y = (v / 255) * H;
          i ? g.lineTo(x, y) : g.moveTo(x, y);
        });
        g.stroke(); g.lineWidth = 1;
      }
      if (this.txAn && performance.now() < this._txUntil + 300) {
        this.txAn.getByteTimeDomainData(tx);
        g.strokeStyle = this._txColor; g.lineWidth = 1.5; g.beginPath();
        tx.forEach((v, i) => {
          const x = (i / tx.length) * W, y = (v / 255) * H;
          i ? g.lineTo(x, y) : g.moveTo(x, y);
        });
        g.stroke(); g.lineWidth = 1;
      }
    };
    draw();
  },
};
