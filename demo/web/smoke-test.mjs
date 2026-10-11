// Headless full-flow test for the web demo. Run: node demo/web/smoke-test.mjs
// Drives both SaphSession roles through loopback "airtime" (async delivery),
// real ECDH/AES-GCM, one injected TASK loss (retry must save it), then all
// four attacks. Exits nonzero on any failure.
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
  let dropNextTask = true, txCount = 0, maxLen = 0;
  globalThis.GG = {
    async send(text) {
      txCount++; maxLen = Math.max(maxLen, text.length);
      assert(text.length <= 138, "frame over budget: " + text.length);
      const m = JSON.parse(text);
      const dst = m.f === "c" ? recep : caller;
      const lost = dropNextTask && m.t === "TASK";
      if (lost) dropNextTask = false;
      else setTimeout(() => dst.onAir(text), 5);
      await new Promise((r) => setTimeout(r, 2));
    },
    setCapture() {},
  };
  await caller.startCall();
  await new Promise((r) => setTimeout(r, 50));
  assert(log.unlocked, "booking completed");
  assert(log.blocked.length === 0, "no false blocks: " + JSON.stringify(log.blocked));
  assert(txCount > 8, "retry fired (tx=" + txCount + ")");
  const nap = () => new Promise((r) => setTimeout(r, 20));
  await caller.replayLast(); await nap();
  assert(log.blocked.length === 1, "caller replay blocked");
  await caller.forgeLast(); await nap();
  assert(log.blocked.length === 2, "caller forgery blocked");
  await recep.replayLast(); await nap();
  assert(log.blocked.length === 3, "recep replay blocked");
  await recep.forgeLast(); await nap();
  assert(log.blocked.length === 4, "recep forgery blocked");
  assert(recep.inventory.dbl.left === 2, "exactly one booking");
  console.log("SMOKE OK (tx=" + txCount + ", maxFrame=" + maxLen + "B)");
})()`, ctx);

if (ctx.__fail) process.exit(1);
