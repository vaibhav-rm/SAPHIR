/* SAPHIR demo choreography: Act 1 talk, Act 2 switch, Act 3 attacks. */
"use strict";

const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let running = false, caller, receptionist, lastTask = null;

const ENGLISH = [
  ["A", "caller", "Hi, I'd like to book a double room for November 2nd, 2 nights, 2 guests."],
  ["B", "receptionist", "Let me check… yes, double rooms available at $120 per night."],
  ["A", "caller", "Great, please book it under Vaibhav."],
  ["B", "receptionist", "Done! Confirmation HB-2026-1142, total $240."],
];
const HANDSHAKE = [
  ["HELLO", "caller", { did: "did:key:zcaller-9f2c", codecs: ["saphir-cbor-v1"], modes: ["audio", "hybrid"] }],
  ["WELCOME", "receptionist", { did: "did:key:zrecep-41ab", selected: "saphir-cbor-v1" }],
  ["KEY1", "caller", { pub: "(X25519 ephemeral, simulated)" }],
  ["KEY2", "receptionist", { pub: "(X25519 ephemeral, simulated)" }],
];
const TASKS = [
  ["TASK", "caller", { intent: "hotel.check", slots: { date: "2026-11-02", room: "double", nights: 2 } }],
  ["TASK", "caller", { intent: "hotel.book", slots: { date: "2026-11-02", room: "double", nights: 2, guests: 2, name: "Vaibhav" } }],
];
const RESULTS = [
  ["RESULT", "receptionist", { ok: true, price: 120, left: 3, quote: 240 }],
  ["RESULT", "receptionist", { ok: true, confirmation: "HB-2026-1142", total: 240 }],
];

function bubble(who, text, cls = "") {
  const d = document.createElement("div");
  d.className = `bubble ${who === "A" ? "me" : "them"} ${cls}`;
  d.textContent = text;
  const box = who === "A" ? $("chatA") : $("chatB");
  box.appendChild(d); box.scrollTop = box.scrollHeight;
  // mirror into the other panel so it reads as a call
  const m = d.cloneNode(true);
  m.className = `bubble ${who === "A" ? "them" : "me"} ${cls}`;
  const other = who === "A" ? $("chatB") : $("chatA");
  other.appendChild(m); other.scrollTop = other.scrollHeight;
  return d;
}

function speak(text) {
  if ($("chkSilent").checked || !("speechSynthesis" in window)) return Promise.resolve();
  return new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1.05; u.onend = resolve; u.onerror = resolve;
    speechSynthesis.speak(u);
    setTimeout(resolve, 6000); // never hang the demo
  });
}

function setPills(mode) {
  for (const id of ["pillA", "pillB"]) {
    $(id).textContent = mode;
    $(id).className = "pill " + (mode === "SAPHIR" ? "saphir" : "english");
  }
}
function sessLine() {
  const s = `sess X25519-sim ${caller.fakeKey.slice(0, 8)}… • ${Audit.frames} frames • ${Audit.bytes}B`;
  $("sessA").textContent = s; $("sessB").textContent = s;
}
function lock(ids, disabled) { ids.forEach((id) => ($(id).disabled = disabled)); }

async function sendFrame(type, sender, payload, opts = {}) {
  const frame = buildFrame(type, sender, payload);
  const bytes = frameBytes(frame);
  const other = sender === "caller" ? "B" : "A";
  const el = bubble(other, `♪ ${type} · ${bytes.length}B · ${hexPreview(bytes)}`, "beep");
  $("chanline").textContent = `sending ${type} (${bytes.length}B, ${bitsOf(bytes).length} FSK bits)…`;
  await playFrame(bytes, (i, n) => {
    el.textContent = `♪ ${type} · ${bytes.length}B · bit ${i}/${n}`;
  });
  $("chanline").textContent = "idle — tones carry real frame bytes (FSK); decode path simulated";
  return { frame, bytes };
}

async function act1() {
  for (const [who, name, line] of ENGLISH) {
    bubble(who, `${name}: ${line}`);
    Audit.add(name === "caller" ? "A→B" : "B→A", "VOICE", name, line.length, "spoken English (TTS)");
    await speak(line);
    if (!running) return;
  }
}

async function act2() {
  bubble("A", "wait — you're AI? let's switch to SAPHIR");
  await sleep(600); if (!running) return;
  for (const [type, sender, payload] of HANDSHAKE) {
    const { frame, bytes } = await sendFrame(type, sender, payload);
    const recv = sender === "caller" ? receptionist : caller;
    const chk = recv.accept(frame); // seq tracking starts
    Audit.add(sender === "caller" ? "A→B" : "B→A", type, sender, bytes.length,
      type.startsWith("KEY") ? "ephemeral pubkey (simulated)" : JSON.stringify(payload).slice(0, 90));
    sessLine();
    if (!running) return;
    void chk;
  }
  caller.established = receptionist.established = true;
  setPills("SAPHIR");
  bubble("A", "🔐 SAPHIR established — structured tasks from here", "beep");
  for (let i = 0; i < TASKS.length; i++) {
    const [ttype, tsender, tpayload] = TASKS[i];
    const { frame, bytes } = await sendFrame(ttype, tsender, tpayload);
    const chk = receptionist.accept(frame);
    lastTask = { frame, bytes };
    Audit.add("A→B", ttype, tsender, bytes.length,
      `${tpayload.intent} ${JSON.stringify(tpayload.slots)}<br><code>→ ${JSON.stringify(RESULTS[i][2])}</code>`);
    const [rtype, rsender, rpayload] = RESULTS[i];
    await sendFrame(rtype, rsender, rpayload);
    Audit.add("B→A", rtype, rsender, frameBytes(buildFrame(rtype, rsender, rpayload)).length,
      JSON.stringify(rpayload));
    bubble("B", `✓ ${tpayload.intent} confirmed`, "beep");
    sessLine();
    if (!running) return;
  }
  lock(["btnReplay", "btnForge"], false);
}

async function attack(kind) {
  if (!lastTask || running) return;
  lock(["btnReplay", "btnForge"], true);
  try {
    if (kind === "replay") {
      bubble("A", "⚔ attacker replays captured TASK tones…", "attack");
      const { bytes } = lastTask;
      await playFrame(bytes, () => {});
      // Receiver runs the REAL replay check on the same frame:
      const chk = receptionist.accept(lastTask.frame);
      Audit.blockedAttack(chk.ok ? "ERROR: replay accepted (bug)" : chk.reason);
      bubble("B", chk.ok ? "accepted?!" : `🛡 BLOCKED — ${chk.reason}`, "attack");
    } else {
      bubble("A", "⚔ attacker forges a TASK (flipped byte)…", "attack");
      const evil = { ...lastTask.frame, seq: lastTask.frame.seq + 50,
                     payload: { ...lastTask.frame.payload, nights: 99 }, tampered: true };
      await playFrame(frameBytes(evil), () => {});
      const chk = receptionist.accept(evil);
      Audit.blockedAttack(chk.ok ? "ERROR: forgery accepted (bug)" : chk.reason);
      bubble("B", chk.ok ? "accepted?!" : `🛡 BLOCKED — ${chk.reason}`, "attack");
    }
  } finally {
    lock(["btnReplay", "btnForge"], false);
  }
}

function reset() {
  running = false; abortAudio();
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  caller = new DemoSession("caller"); receptionist = new DemoSession("receptionist");
  lastTask = null; _seq = 0;
  $("chatA").innerHTML = ""; $("chatB").innerHTML = "";
  setPills("ENGLISH");
  $("sessA").textContent = "no session"; $("sessB").textContent = "no session";
  Audit.reset();
  lock(["btnRun", "btnAct1", "btnAct2"], false);
  lock(["btnReplay", "btnForge"], true);
}

async function guarded(fn, btns) {
  if (running) return;
  running = true; lock(btns, true);
  try { await fn(); } finally { running = false; lock(["btnRun", "btnAct1", "btnAct2"], false); }
}

window.addEventListener("DOMContentLoaded", () => {
  reset(); startScopes();
  $("btnRun").onclick = () => guarded(async () => { await act1(); await act2(); }, ["btnRun", "btnAct1", "btnAct2"]);
  $("btnAct1").onclick = () => guarded(act1, ["btnRun", "btnAct1", "btnAct2"]);
  $("btnAct2").onclick = () => guarded(act2, ["btnRun", "btnAct1", "btnAct2"]);
  $("btnReplay").onclick = () => attack("replay");
  $("btnForge").onclick = () => attack("forge");
  $("btnReset").onclick = reset;
});
