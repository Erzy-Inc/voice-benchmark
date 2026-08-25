"""E2E track: full voice-agent loop latency (STT finalize → LLM first token → TTS first audio)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class LLMAdapter(Protocol):
    async def first_token(self, prompt: str) -> tuple[str, float]:
        """Return (text, latency_ms to first token)."""
        ...


class TTSAdapter(Protocol):
    async def first_audio(self, text: str) -> float:
        """Return ms until first audio byte."""
        ...


@dataclass
class E2EConfig:
    stt_provider_id: str
    llm_model: str
    tts_voice_id: str


async def run_e2e_turn(stt_finalize_ms: float, llm: LLMAdapter, tts: TTSAdapter, prompt: str) -> dict:
    """Compose the loop from a measured STT finalize + live LLM/TTS legs."""
    _, llm_ms = await llm.first_token(prompt)
    tts_ms = await tts.first_audio(prompt)
    total = stt_finalize_ms + llm_ms + tts_ms
    return {
        "stt_finalize_ms": round(stt_finalize_ms, 2),
        "llm_first_token_ms": round(llm_ms, 2),
        "tts_first_audio_ms": round(tts_ms, 2),
        "e2e_total_ms": round(total, 2),
    }
