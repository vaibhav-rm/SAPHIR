"""Sidecar audit log: every frame rendered human-readable (JSONL)."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AuditLog:
    path: Path | str
    entries: list = field(default_factory=list)

    def record(self, direction: str, env_type: str, sender: str, seq: int,
               nbytes: int, summary: str, decrypted: dict | None = None):
        e = {"t": time.time(), "dir": direction, "type": env_type, "sender": sender,
             "seq": seq, "bytes": nbytes, "summary": summary,
             "decrypted": decrypted}
        self.entries.append(e)
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(json.dumps(e, default=str) + "\n")
        return e

    def human_transcript(self) -> str:
        lines = []
        for e in self.entries:
            d = e.get("decrypted")
            extra = f" -> {d}" if d else ""
            lines.append(f"[{e['dir']}] {e['type']} from {e['sender']} seq={e['seq']} ({e['bytes']}B): {e['summary']}{extra}")
        return "\n".join(lines)
