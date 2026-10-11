// Headless tests for the web demo. Run: node demo/web/smoke-test.mjs
// Scenario A (air works): loopback delivery, real crypto, one injected TASK
//   loss (retry must save it), then all four attacks.
// Scenario B (mic deaf): delivery ONLY via the both-mode direct feed.
// Both must complete with zero false blocks and exactly one booking.
import fs from "fs";
import vm from "vm";
import path from "path";
import { fileURLToPath } from "url";

const dir = path.dirname(fileURLToPath(import.meta.url));
const load = (f) => fs.readFileSync(path.join(dir, f), "utf8");

const ctx = vm.createContext({
  console, setTimeout, clearTimeout, process,
  crypto, TextEncoder, TextDecoder, URLSearchParams, btoa, atob,
  // outer-realm typed arrays: Node WebCrypto rejects foreign-realm views
  Uint8Array, Uint16Array, Uint32Array, Int8Array, ArrayBuffer, DataView,
});
vm.runInContext(load("crypto.js"), ctx);
vm.runInContext(
  load("session.js").replace("const ACK_TIMEOUT = 20000;", "const ACK_TIMEOUT = 400;"),
  ctx
);

await vm.runInContext(`(async () => {
  const assert = (c, m) => { if (!c) { globalThis.__fail = m; throw new Error(m); } };
  const nap = (ms) => new Promise((r) => setTimeout(r, ms));

  async function scenario(deaf, tag) {
    const log = { blocked: [], unlocked: false };
    const ui = {
      say: () => {}, speak: async () => {}, sessionLine: () => {}, setMode: () => {},
      mood: () => {}, robotBeep: () => {}, chan: () => {},
      banner: () => {}, audit: () => {},
      blocked: (r) => log.blocked.push(r),
      unlockAttacks: () => (log.unlocked = true),
    };
    const caller = new SaphSession("caller", ui);
    const recep = new SaphSession("receptionist", ui);
    caller.directDelay = 15; recep.directDelay = 15;
    if (deaf) { caller.directPeer = recep; recep.directPeer = caller; }
    let dropNextTask = !deaf, txCount = 0, maxLen = 0;
    globalThis.GG = {
      async send(text) {
        txCount++; maxLen = Math.max(maxLen, text.length);
        assert(text.length <= 138, tag + ": frame over budget: " + text.length);
        const m = JSON.parse(text);
        if (!(dropNextTask && m.t === "TASK")) {
          const dst = m.f === "c" ? recep : caller;
          if (!deaf) setTimeout(() => dst.onAir(text), 5); // air works
          // deaf mode: mic hears nothing — direct feed (scheduled by sendRaw) saves it
        } else dropNextTask = false;
        await nap(2);
      },
      setCapture() {},
    };
    await caller.startCall();
    await nap(80);
    assert(log.unlocked, tag + ": booking completed");
    assert(log.blocked.length === 0, tag + ": no false blocks: " + JSON.stringify(log.blocked));
    assert(recep.inventory.dbl.left === 2, tag + ": exactly one booking");
    console.log(tag + " OK (tx=" + txCount + ", maxFrame=" + maxLen + "B)");
    return { caller, recep, log };
  }

  const a = await scenario(false, "air");
  assert(a.caller && a.recep, "scenario A sessions");
  // attacks on the air scenario (lastCrypto = RESULT / TASK)
  const { caller, recep, log } = a;
  await caller.replayLast(); await nap(30);
  assert(log.blocked.length === 1, "caller replay blocked");
  await caller.forgeLast(); await nap(30);
  assert(log.blocked.length === 2, "caller forgery blocked");
  await recep.replayLast(); await nap(30);
  assert(log.blocked.length === 3, "recep replay blocked");
  await recep.forgeLast(); await nap(30);
  assert(log.blocked.length === 4, "recep forgery blocked");
  console.log("attacks OK");

  await scenario(true, "deaf-mic+direct");
  console.log("ALL SMOKE OK");
})()`, ctx);

if (ctx.__fail) process.exit(1);
