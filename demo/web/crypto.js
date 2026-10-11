/* Real session crypto: ECDH P-256 + AES-GCM with fresh random IVs per seal.
 * Random (not deterministic) IVs are load-bearing beyond hygiene: ggwave shows
 * content-dependent decode misses, so a retry must re-seal to FRESH bytes —
 * retransmitting identical bytes would replay a poison payload forever.
 */
"use strict";

const b64e = (bytes) => btoa(String.fromCharCode(...new Uint8Array(bytes)));
const b64d = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

function randomIv() {
  return crypto.getRandomValues(new Uint8Array(12));
}

const Crypto2 = {
  async genDH() {
    const kp = await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, true, ["deriveKey"]);
    const raw = await crypto.subtle.exportKey("raw", kp.publicKey);
    return { kp, pubB64: b64e(raw) };
  },
  async derive(dh, peerB64) {
    const peerRaw = b64d(peerB64);
    const peerKey = await crypto.subtle.importKey("raw", peerRaw,
      { name: "ECDH", namedCurve: "P-256" }, false, []);
    return crypto.subtle.deriveKey({ name: "ECDH", public: peerKey }, dh.kp.privateKey,
      { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]);
  },
  async seal(aesKey, plaintext) {
    const iv = randomIv();
    const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv },
      aesKey, new TextEncoder().encode(plaintext));
    return { iv: b64e(iv), ct: b64e(ct) };
  },
  async open(aesKey, ivB64, ctB64) {
    const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64d(ivB64) },
      aesKey, b64d(ctB64));
    return new TextDecoder().decode(pt);
  },
};

/* short-slot querystring codec, mirrors src/saphir/codec.py */
const qsEncode = (slots) => Object.entries(slots)
  .map(([k, v]) => `${k}=${v}`).join("&");
const qsDecode = (s) => Object.fromEntries(s.split("&").map((p) => {
  const i = p.indexOf("="); return [p.slice(0, i), p.slice(i + 1)];
}));
