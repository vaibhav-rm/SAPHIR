"""Cost/latency model for paper numbers (document assumptions in paper)."""
from __future__ import annotations
from dataclasses import dataclass

# Assumptions (tune + cite in paper):
CHARS_PER_TOKEN = 4.0
TTS_COST_PER_1K_CHARS = 0.015  # $ ElevenLabs-ish
STT_COST_PER_MIN = 0.006       # $ Whisper-ish
LLM_COST_PER_1K_TOK = 0.002
# ggwave audible-fast ~32-64 Bps in quiet room; conservative 32 here.
# Wall-clock is SIMILAR to speech; the win is neural compute (no TTS/STT/LLM
# per turn — tone decode is ~ms of CPU), not raw seconds. Report both.
GGWAVE_GOODPUT_BPS = 32.0      # audible-fast conservative, bytes/sec
SPEECH_CHARS_PER_SEC = 14.0    # ~800 chars/min


@dataclass
class DialogueMetrics:
    english_chars: int
    saphir_bytes: int
    n_turns: int = 4

    @property
    def english_tokens(self):
        return self.english_chars / CHARS_PER_TOKEN

    @property
    def speech_loop_seconds(self):
        # STT + LLM + TTS per turn, rough
        return self.n_turns * (self.english_chars / self.n_turns / SPEECH_CHARS_PER_SEC + 1.2)

    @property
    def saphir_seconds(self):
        return self.saphir_bytes / GGWAVE_GOODPUT_BPS + 0.4 * self.n_turns

    @property
    def speech_cost_usd(self):
        return (self.english_chars / 1000 * TTS_COST_PER_1K_CHARS
                + self.speech_loop_seconds / 60 * STT_COST_PER_MIN
                + self.english_tokens / 1000 * LLM_COST_PER_1K_TOK * self.n_turns)

    def summary(self) -> dict:
        return {"english_chars": self.english_chars, "saphir_bytes": self.saphir_bytes,
                "speech_sec": round(self.speech_loop_seconds, 2),
                "saphir_sec": round(self.saphir_seconds, 2),
                "speech_cost_usd": round(self.speech_cost_usd, 4)}
