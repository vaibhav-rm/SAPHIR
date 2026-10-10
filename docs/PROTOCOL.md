# SAPHIR Wire Spec v0.1 (MVP)

Transport: any ordered byte pipe. Reference acoustic mapping: 1 envelope ≈ 1–2
ggwave audible transmissions (ggwave reliable payload per tx is well under 200B
in noisy rooms; handshake frames are the largest).

Frame: `u32be len || CBOR({v, type, seq, sender, nonce, payload})`.
Cap: `MAX_MSG_BYTES = 200` for TASK/RESULT (see `src/saphir/protocol.py`).

## Messages

| Type | Dir | Plaintext payload | Notes |
|---|---|---|---|
| HELLO | A→B | {agent_id, did, codecs, modes, nonce(16B), ts} | ephemeral `did:key:z…` |
| WELCOME | B→A | {… + selected} | codec negotiation |
| KEY1 | A→B | {pub: 32B} | X25519 ephemeral |
| KEY2 | B→A | {pub: 32B} | both derive HKDF-SHA256 → 32B ChaCha key |
| TASK | ↔ | ChaCha20Poly1305(cbor({intent, slots, ontology, ts})), aad=sender, nonce=12B | replay-protected |
| RESULT | ↔ | ChaCha(…) | same AEAD path |
| ERROR / BYE | ↔ | {code, msg} | plaintext |

## Measured sizes (CBOR-encoded, this repo)

| Message | Bytes | Notes |
|---|---|---|
| HELLO | ~194 | largest; shrink path: 8B nonce, shorter DID |
| WELCOME | ~195 | echo + selected codec |
| KEY1 / KEY2 | ~107 / 113 | 32B pubkey + envelope |
| TASK hotel.check | ~182 | encrypted |
| TASK hotel.book | ~202 | encrypted, exceeds single ggwave tx → needs 2 frames |
| RESULT | ~126–139 | encrypted |

Shrinking below 140B single-frame for all messages is open work (short keys,
array-form CBOR, slot dictionary). The cap is enforced in `encode_envelope()`.

## Security properties (MVP)

- Forward secrecy per pairing (ephemerals discarded after BYE).
- Confidentiality + integrity for TASK/RESULT (ChaCha20Poly1305, AAD = sender id).
- Replay rejection: per-session `seen_seq` + `(nonce, ct)` set.
- Downgrade flagging: peer offering no `saphir-cbor-v1` never gets beeps;
  session stays in English with an explicit log entry.

NOT in v0.1: mutual PKI/DID verification, group (MLS) sessions, ultrasound
modes, DoS-resistant MAC layer, multi-frame fragmentation/reassembly.
