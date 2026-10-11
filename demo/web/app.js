/* SAPHIR demo app: roles (?role=caller|receptionist|both), boot, buttons. */
"use strict";

const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);

const UI = {
  frames: 0, bytes: 0, blocked: 0,

  say(role, text, english, attack = false) {
    const show = (panel, cls) => {
      const d = document.createElement("div");
      d.className = `msg ${cls}` + (attack ? " attack" : "") + (english ? "" : " beep");
      d.textContent = text;
      const box = $(panel === "caller" ? "feedC" : "feedR");
      box.appendChild(d); box.scrollTop = box.scrollHeight;
    };
    show(role, "me");
    show(role === "caller" ? "receptionist" : "caller", "them");
    if (english) this.mood(role, "speaking");
  },
  speak(text) {
    if (!("speechSynthesis" in window)) return Promise.resolve();
    speechSynthesis.cancel();
    return new Promise((resolve) => {
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 1.08; u.onend = resolve; u.onerror = resolve;
      speechSynthesis.speak(u);
      setTimeout(resolve, 9000); // never hang the demo
    });
  },
  setMode(mode) {
    const b = $("modebanner");
    b.textContent = mode;
    b.className = "mode " + (mode === "SAPHIR" ? "saphir" : "english");
    if (mode === "SAPHIR") {
      b.classList.add("glitch");
      setTimeout(() => b.classList.remove("glitch"), 900);
    }
  },
  mood(role, m) {
    const el = $(role === "caller" ? "dotC" : "dotR");
    if (!el) return;
    el.classList.remove("speaking", "beeping", "listening", "blocked");
    if (m) el.classList.add(m);
  },
  robotBeep(role, on) { this.mood(role, on ? "beeping" : null); },
  sessionLine(t) { $("sessline").textContent = t; },
  chan(t) { $("chanline").textContent = t; },
  banner(t) {
    const b = $("banner"); b.textContent = t; b.hidden = false;
    clearTimeout(this._t); this._t = setTimeout(() => (b.hidden = true), 9000);
  },
  audit(dir, type, nbytes, text) {
    this.frames++; this.bytes += nbytes;
    $("mFrames").textContent = this.frames;
    $("mBytes").textContent = this.bytes;
    const li = document.createElement("li");
    li.innerHTML = `<b>[${dir}] ${type}</b> · ${nbytes}B<br><code>${text}</code>`;
    $("audit").prepend(li);
  },
  blocked(reason) {
    this.blocked++;
    $("mBlocked").textContent = this.blocked;
    const li = document.createElement("li");
    li.className = "bad";
    li.innerHTML = `<b>🛡 BLOCKED</b> · ${reason}`;
    $("audit").prepend(li);
    this.banner(`🛡 Attack blocked — ${reason}`);
    const r = role === "receptionist" ? "receptionist" : "caller";
    this.mood(r, "blocked");
    setTimeout(() => this.mood(r, null), 1600);
  },
  unlockAttacks() { $("btnReplay").disabled = $("btnForge").disabled = false; },
};

let role = params.get("role") || null;
let callerSess = null, recepSess = null, booted = false;

async function boot() {
  if (booted) return; booted = true;
  const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
  await GG.init(ctx);
  GG.scope($("wave"));
  try { await GG.startMic(); }
  catch (e) {
    UI.banner("⚠ Mic blocked — allow microphone access, then Reset. (localhost or HTTPS required)");
  }
  GG.onText = (text) => {
    if (callerSess) callerSess.onAir(text);
    if (recepSess) recepSess.onAir(text);
  };
  callerSess = new SaphSession("caller", UI);
  recepSess = new SaphSession("receptionist", UI);
  UI.sessionLine("ggwave ready · audible fast · mic live — press Start");
}

window.addEventListener("DOMContentLoaded", () => {
  if (!role) { $("picker").hidden = false; return; }
  $("controls").hidden = false;
  $("rolebadge").textContent = "role: " + role;
  $("btnStart").onclick = async () => {
    $("btnStart").disabled = true;
    await boot();
    UI.mood("caller", "listening"); UI.mood("receptionist", "listening");
    if (role === "caller" || role === "both") {
      $("rolebadge").textContent =
        role === "both" ? "both roles · one device (loopback)" : "you are the caller 📞";
      await callerSess.startCall();
    } else {
      $("rolebadge").textContent = "you are the receptionist 🏨 — listening…";
      UI.banner("Listening as receptionist — start the caller on the other device.");
    }
  };
  const sess = () => (role === "receptionist" ? recepSess : callerSess);
  $("btnReplay").onclick = async () => {
    $("btnReplay").disabled = true;
    try { await sess().replayLast(); } finally { $("btnReplay").disabled = false; }
  };
  $("btnForge").onclick = async () => {
    $("btnForge").disabled = true;
    try { await sess().forgeLast(); } finally { $("btnForge").disabled = false; }
  };
  $("btnReset").onclick = () => location.reload();
});

function pick(r) { location.search = "?role=" + r; }
