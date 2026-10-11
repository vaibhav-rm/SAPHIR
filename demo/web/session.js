/* SAPHIR demo session: real handshake + AES-GCM tasks + replay sets over ggwave.
 *
 * Wire (ASCII, every message <= 138B — enforced before TX):
 *   HELLO   {"t":"HELLO","f":"c","did":"9f2c"}
 *   WELCOME {"t":"WELCOME","f":"r","did":"41ab","sel":"std"}
 *   KEY1/2  {"t":"KEY1","f":"c","p":"<b64 P-256 pub>"}
 *   TASK    {"t":"TASK","q":1,"f":"c","i":"hb","v":"<b64 iv>","c":"<b64 AES-GCM slots>"}
 *   RESULT  {"f":"r","q":1,"t":"RESULT","v":"<b64 iv>","c":"<b64 AES-GCM result>"}
 *   DONE    {"t":"DONE","f":"c"}
 *
 * NOTE on key order: the ggwave implementation shows content-dependent
 * first-try decode sensitivity (some shapes fail deterministically in-process;
 * verified with the vendored WASM + Python builds). RESULT uses the verified
 * f-first shape. Shapes are regression-guarded by evals/ggwave_frames.py.
 *
 * Reliability is response-driven retransmission (zero extra airtime — the
 * protocol is lockstep, so each reply doubles as the ACK):
 *   HELLO→WELCOME→KEY1→KEY2→TASK→RESULT→…→DONE
 */
"use strict";

const MAX_GG = 138;
const ACK_TIMEOUT = 20000;
const ACK_TRIES = 3;

class SaphSession {
  constructor(role, ui) {
    this.role = role;            // 'caller' | 'receptionist'
    this.me = role === "caller" ? "c" : "r";
    this.ui = ui;
    this.did = (Math.random().toString(16).slice(2, 6));
    this.q = 0;
    this.seen = new Set();       // "sender:q" — real replay protection
    this.opened = new Map();     // key -> decoded RESULT (idempotent re-delivery)
    this.taskCache = new Map();  // key -> RESULT body (resend on legit retry)
    this.dh = null; this.aes = null;
    this.established = false;
    this.lastHeard = null;       // raw string, for the replay demo
    this.lastCrypto = null;      // last encrypted frame — the attacks target this
    this.done = false;
    this.echoSent = new Set();   // our own TX heard back by our mic: ignore
    this.recent = new Map();     // raw text -> ms: mic re-decodes one burst N times
    this.welcomed = false;
    this.waiters = [];           // {types, resolve} — response-driven retry
    this.inventory = { dbl: { price: 120, left: 3 }, sng: { price: 80, left: 5 } };
  }

  /* ---------- transport ---------- */
  async sendRaw(obj) {
    const text = JSON.stringify(obj);
    if (text.length > MAX_GG) throw new Error(`frame ${text.length}B over budget`);
    this.ui.robotBeep(this.role, true);
    this.ui.audit(this.role === "caller" ? "A→B" : "B→A", obj.t, text.length, text);
    await GG.send(text);
    this.echoSent.add(text);
    if (this.echoSent.size > 60) this.echoSent.delete(this.echoSent.values().next().value);
    this.ui.robotBeep(this.role, false);
    GG.setCapture(true);
    return text;
  }

  // Send until a frame of one of expectTypes arrives (it doubles as the ACK).
  // build is a thunk re-run every try so retries re-seal with fresh IVs —
  // retransmitting identical bytes would replay a poison payload forever.
  async sendRecv(build, expectTypes) {
    for (let i = 1; i <= ACK_TRIES; i++) {
      const wait = this._waitFor(expectTypes, ACK_TIMEOUT); // arm BEFORE tx (loopback-safe)
      const obj = typeof build === "function" ? await build() : build;
      await this.sendRaw(obj);
      this.ui.chan(`waiting for ${expectTypes.join("/")}… try ${i}/${ACK_TRIES}`);
      const got = await wait;
      if (got) { this.ui.chan("idle"); return got; }
    }
    this.ui.chan("idle");
    return null;
  }

  _waitFor(types, ms) {
    return new Promise((resolve) => {
      const w = { types, resolve };
      this.waiters.push(w);
      setTimeout(() => {
        const i = this.waiters.indexOf(w);
        if (i >= 0) this.waiters.splice(i, 1);
        resolve(null);
      }, ms);
    });
  }

  async onAir(text, direct = false) {
    let m;
    try { m = JSON.parse(text); } catch (_) { return; } // not ours
    if (!m.t || m.f === this.me) return;                 // wrong format / own echo
    if (!direct && this.echoSent.has(text)) return;      // our own attack TX heard back
    this.lastHeard = text;
    if (m.c) this.lastCrypto = text;
    const now = Date.now();                              // same burst decoded again?
    if (!direct && this.recent.has(text) && now - this.recent.get(text) < 3000) return;
    this.recent.set(text, now);
    this.ui.audit(m.f === "c" ? "A→B" : "B→A", m.t + " ⇄rx", text.length,
      (direct ? "[attack path] " : "") + text.slice(0, 140));
    for (const w of this.waiters.splice(0))              // wake up sendRecv first…
      if (w.types.includes(m.t)) w.resolve(m);
    if (this.role === "caller") await this._callerRecv(m, direct);
    else await this._recepRecv(m, direct);
  }

  /* ---------- caller (initiator, lockstep) ---------- */
  async startCall() {
    const ui = this.ui;
    ui.say("caller", "Hi, I'd like to book a double room for November 2nd, 2 nights, 2 guests.", true);
    await ui.speak("Hi, I'd like to book a double room for November 2nd, 2 nights, 2 guests.");
    ui.say("receptionist", "Let me check… yes, double rooms available at $120 per night.", true);
    await ui.speak("Let me check. Yes, double rooms are available at 120 dollars per night.");
    ui.say("caller", "Wait — you're AI? Let's switch to SAPHIR.", true);
    await ui.speak("Wait, you are AI? Let's switch to SAPHIR.");
    ui.setMode("SAPHIR");
    const noAir = () => ui.banner("📻 No reply heard — check speakers + mic volume, then Reset.");

    const w = await this.sendRecv({ t: "HELLO", f: "c", did: this.did }, ["WELCOME"]);
    if (!w) return noAir();
    this.dh = await Crypto2.genDH();
    const k2 = await this.sendRecv({ t: "KEY1", f: "c", p: this.dh.pubB64 }, ["KEY2"]);
    if (!k2) return noAir();
    if (!this.aes) this.aes = await Crypto2.derive(this.dh, k2.p);
    this.established = true;
    ui.sessionLine("Paired · ECDH P-256 → AES-GCM-256 · response-driven retry armed");
    ui.say("caller", "🔐 SAPHIR established — structured tasks from here", false);

    const r1 = await this._doTask("hc", { d: "261102", r: "dbl", n: 2 });
    if (!r1) return noAir();
    const r2 = await this._doTask("hb", { d: "261102", r: "dbl", n: 2, g: 2, nm: "Vaibhav" });
    if (!r2) return noAir();
    await this.sendRaw({ t: "DONE", f: "c" }); // releases the last RESULT retry
    this.done = true;
    ui.say("caller", `Booking complete. Confirmation ${r2.cf}, $${r2.total}. Zero English wasted after the switch.`, false);
    ui.banner("✅ Booking complete — authenticated, encrypted, audited.");
    ui.unlockAttacks();
  }

  async _doTask(intent, slots) {
    this.q++;
    const q = this.q;
    const build = async () => {
      const s = await Crypto2.seal(this.aes, qsEncode(slots));
      return { t: "TASK", q, f: "c", i: intent, v: s.iv, c: s.ct };
    };
    const m = await this.sendRecv(build, ["RESULT"]);
    if (!m) return null;
    const res = await this._openResult(m);
    if (res) this.ui.say("caller", `✓ ${intent} confirmed — ${res._human}`, false);
    return res;
  }

  async _callerRecv(m, direct = false) {
    // Late arrivals outside sendRecv windows (belated duplicates): routing only,
    // guarded by the same checks so nothing double-processes.
    if (m.t === "RESULT") await this._openResult(m, direct);
  }

  async _openResult(m, attack = false) {
    const key = `r:${m.q}`;
    if (this.seen.has(key)) {
      // Seen before: silent idempotent re-delivery, unless this IS the attack.
      if (attack || !this.opened.has(key)) this.ui.blocked(`replay: seq ${m.q} reused`);
      return this.opened.get(key) || null;
    }
    let pt;
    try { pt = await Crypto2.open(this.aes, m.v, m.c); }
    catch (_) { this.ui.blocked("auth tag mismatch (InvalidTag)"); return null; }
    this.seen.add(key);
    const r = qsDecode(pt);
    r._intent = r.cf ? "hotel.book" : "hotel.check";
    r._human = r.cf ? `confirmation ${r.cf}, $${r.total}` : `$${r.price}/night, ${r.left} left`;
    this.opened.set(key, r);
    return r;
  }

  /* ---------- receptionist (responder, lockstep loop) ---------- */
  async _recepRecv(m, direct = false) {
    if (m.t === "HELLO") {
      if (this.welcomed) return;
      this.welcomed = true;
      const ui = this.ui;
      ui.setMode("SAPHIR");
      ui.say("receptionist", "An AI caller! Switching to SAPHIR.", true);
      await ui.speak("An AI caller! Switching to SAPHIR.");
      await this._exchange(await this.sendRecv(
        { t: "WELCOME", f: "r", did: this.did, sel: "std" }, ["KEY1"]));
    } else if (direct && m.t === "TASK") {
      // Attack simulation: run the REAL checks, never execute.
      await this._attackTask(m);
    }
  }

  async _attackTask(m) {
    const ui = this.ui, key = `c:${m.q}`;
    if (this.seen.has(key)) { ui.blocked(`replay: seq ${m.q} reused`); return; }
    try { qsDecode(await Crypto2.open(this.aes, m.v, m.c)); }
    catch (_) { ui.blocked("auth tag mismatch (InvalidTag)"); return; }
    ui.audit("SYS", "NOTE", 0, "attack frame unexpectedly valid — ignored, never executed");
  }

  async _exchange(m) {
    const ui = this.ui;
    if (!m || m.t === "DONE") {
      if (m) ui.banner("✅ Exchange complete — audited on both sides.");
      else ui.banner("📻 No reply heard — check speakers + mic volume, then Reset.");
      return;
    }
    if (m.t === "KEY1") {
      if (!this.dh) this.dh = await Crypto2.genDH();
      if (!this.aes) this.aes = await Crypto2.derive(this.dh, m.p);
      this.established = true;
      ui.sessionLine("Paired · ECDH P-256 → AES-GCM-256 · response-driven retry armed");
      ui.unlockAttacks();
      await this._exchange(await this.sendRecv(
        { t: "KEY2", f: "r", p: this.dh.pubB64 }, ["TASK", "DONE"]));
      return;
    }
    if (m.t === "TASK") {
      const key = `c:${m.q}`;
      let res, fresh = false;
      if (this.seen.has(key) && this.taskCache.has(key)) {
        // Legitimate sender retry (its RESULT was lost): resend cached result, no re-execution.
        res = this.taskCache.get(key);
        ui.audit("B→A", "RESEND", 0, `duplicate TASK q=${m.q} — cached RESULT re-sent, booking untouched`);
      } else {
        if (this.seen.has(key)) { ui.blocked(`replay: seq ${m.q} reused`); return; }
      let slots;
      try { slots = qsDecode(await Crypto2.open(this.aes, m.v, m.c)); }
      catch (_) { ui.blocked("auth tag mismatch (InvalidTag)"); return; }
      this.seen.add(key);
      res = this._handle(m.i, slots);
      this.taskCache.set(key, res);
      fresh = true;
      }
      this.q++;
      const myQ = this.q, myRes = res;
      const buildRes = async () => {
        const s = await Crypto2.seal(this.aes, qsEncode(myRes));
        // f-first key order: verified ggwave-friendly shape (see file header).
        return { f: "r", q: myQ, t: "RESULT", v: s.iv, c: s.ct };
      };
      const nxt = await this.sendRecv(buildRes, ["TASK", "DONE"]);
      if (fresh) ui.say("receptionist", `✓ ${m.i} → ${JSON.stringify(res)}`, false);
      await this._exchange(nxt);
    }
  }

  _handle(intent, s) {
    const room = this.inventory[s.r];
    if (intent === "hc") {
      if (room && room.left > 0) return { ok: "1", price: String(room.price), left: String(room.left) };
      return { ok: "0", err: "soldout" };
    }
    if (intent === "hb") {
      if (room && room.left > 0) {
        room.left--;
        return { ok: "1", cf: "HB-1142", total: String(room.price * Number(s.n || 1)) };
      }
      return { ok: "0", err: "soldout" };
    }
    return { ok: "0", err: "unknown" };
  }

  /* ---------- attacks: replay / forge the last overheard frame, for real ---- */
  async replayLast() {
    const target = this.lastCrypto || this.lastHeard;
    if (!target) return;
    this.ui.say(this.role, "⚔ replaying captured tones…", false, true);
    this.echoSent.add(target); // mic will hear it too: suppress, process once
    await GG.send(target); // same bytes, real airtime
    GG.setCapture(true);
    await this.onAir(target, true); // seen-set rejects it
  }

  async forgeLast() {
    const target = this.lastCrypto;
    if (!target) { this.ui.banner("Nothing encrypted overheard yet — run the switch first."); return; }
    let m;
    try { m = JSON.parse(target); } catch (_) { return; }
    m.c = (m.c[0] === "A" ? "B" : "A") + m.c.slice(1); // flip one b64 char
    m.q = 500 + Math.floor(Math.random() * 500);       // fresh seq: forces the AUTH check, not replay
    const evil = JSON.stringify(m);
    this.echoSent.add(evil);
    this.ui.say(this.role, "⚔ forging a TASK (flipped byte)…", false, true);
    await GG.send(evil);
    GG.setCapture(true);
    await this.onAir(evil, true); // AES-GCM open fails
  }
}
