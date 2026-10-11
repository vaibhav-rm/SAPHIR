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
    this.protocol = gg.ProtocolId.GGWAVE_PROTOCOL_AUDIBLE_FAST;
    this.ready = true;
  },

  // Encode text -> real ggwave waveform -> play. Returns airtime ms.
  async send(text) {
    if (!this.ready) throw new Error("ggwave not initialized (click Start first)");
    if (text.length > 138) throw new Error(`payload ${text.length}B exceeds 138B ggwave budget`);
    this.setCapture(false);
    const wav = this.gg.encode(this.inst, text, this.protocol, 10);
    const buf = this.ctx.createBuffer(1, wav.length, this.ctx.sampleRate);
    buf.getChannelData(0).set(wav);
    const src = this.ctx.createBufferSource();
    src.buffer = buf; src.connect(this.ctx.destination);
    const ms = (wav.length / this.ctx.sampleRate) * 1000;
    src.start();
    await new Promise((r) => { src.onended = r; setTimeout(r, ms + 400); });
    await new Promise((r) => setTimeout(r, 250)); // tail guard
    return ms;
  },

  setCapture(on) {
    if (on === this.capturing) return;
    this.capturing = on;
    document.getElementById("micdot").className = "dot " + (on ? "on" : "off");
    document.getElementById("miclabel").textContent = on ? "listening" : "mic paused";
    if (this.recorder) {
      try {
        if (on) { this.mediaStream.connect(this.recorder); this.recorder.connect(this.ctx.destination); }
        else { this.mediaStream.disconnect(this.recorder); this.recorder.disconnect(this.ctx.destination); }
      } catch (_) {}
    }
  },

  async startMic() {
    const constraints = { audio: { echoCancellation: false, autoGainControl: false, noiseSuppression: false } };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    this.mediaStream = this.ctx.createMediaStreamSource(stream);
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
    this.setCapture(true); // connects mic -> recorder -> out; onaudioprocess now fires
  },
};
