# SAPHIR Wire Spec v0.1 (MVP)

Transport: any ordered byte pipe. Reference acoustic mapping: 1 envelope ≈ 1
ggwave audible transmission (all current frames fit the single-frame budget).

Frame: `u32be len || CBOR({v, type, seq, sender, nonce, payload})`.
Cap: `MAX_MSG_BYTES = 200` for TASK/RESULT (see `src/saphir/protocol.py`).

## Messages

| Type | Dir | Plaintext payload | Notes |
|---|---|---|---|
| HELLO | A→B | {did, codec:[int], modes:int, ts:int, need?, have?, bloom?} | need = id or open string; have = bitmask; empties omitted |
| WELCOME | B→A | {did, sel:int, modes:int, ts:int, for?, match?:2\|1\|0} | exact/maybe/no verdict |
| KEY1 | A→B | {pub: 32B} | X25519 ephemeral |
| KEY2 | B→A | {pub: 32B} | both derive HKDF-SHA256 → 32B ChaCha key |
| TASK | ↔ | ChaCha20Poly1305(cbor({intent, slots, ontology, ts})), aad=sender, nonce=12B | replay-protected |
| RESULT | ↔ | ChaCha(…) | same AEAD path |
| ERROR / BYE | ↔ | {code, msg} | plaintext |

## Measured sizes (CBOR-encoded, this repo)

| Message | Bytes | Notes |
|---|---|---|
| HELLO | ~107–130 | bare / with need / with offers; all single-frame |
| WELCOME | ~132 | verdict fields included, single-frame |
| KEY1 / KEY2 | ~107 / 113 | 32B pubkey + envelope |
| TASK hotel.check | ~117 | encrypted, compact encoding — fits single frame |
| TASK hotel.book | ~131 | encrypted, compact — fits single frame |
| TASK taxi.request / taxi.book | ~128 / 139 | non-default ontology (`st1` tag), fits single frame |
| RESULT | ~126–139 | encrypted |

Single-frame throughout: handshake compaction (dropped duplicate id/nonce,
int codebooks, short DIDs, int timestamps) brought HELLO/WELCOME under the
140B budget alongside tasks. Hand dictionaries are demo-scale by design;
schema-driven dictionaries negotiated in HELLO are the scalable version
(future work, listed as an RQ in the manuscript).

## Security properties (MVP)

- Forward secrecy per pairing (ephemerals discarded after BYE).
- Confidentiality + integrity for TASK/RESULT (ChaCha20Poly1305, AAD = sender id).
- Replay rejection: per-session `seen_seq` + `(nonce, ct)` set.
- Downgrade flagging: peer offering no `saphir-cbor-v1` never gets beeps;
  session stays in English with an explicit log entry.

NOT in v0.1: mutual PKI/DID verification, group (MLS) sessions, ultrasound
modes, DoS-resistant MAC layer, multi-frame fragmentation/reassembly.
