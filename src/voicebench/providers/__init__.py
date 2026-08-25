"""Registry of benchmark providers.

Each module exports its provider classes. Adding a vendor =
new module + one line below. See providers/README.md.
"""
from __future__ import annotations

from .assemblyai import AssemblyAIUniversal35Pro
from .base import BaseProvider
from .cartesia import CartesiaInk
from .deepgram import DeepgramNova3, EchoProvider
from .elevenlabs import ElevenLabsScribeV2Realtime
from .soniox import SonioxSTTRTV5

PROVIDERS: dict[str, BaseProvider] = {
    p.provider_id: p
    for p in [
        EchoProvider(),
        DeepgramNova3(),
        AssemblyAIUniversal35Pro(),
        ElevenLabsScribeV2Realtime(),
        SonioxSTTRTV5(),
        CartesiaInk(),
    ]
}

__all__ = ["PROVIDERS", "BaseProvider"]


def get_provider(provider_id: str) -> BaseProvider:
    if provider_id not in PROVIDERS:
        raise KeyError(
            f"unknown provider '{provider_id}'. Registered: {sorted(PROVIDERS)}"
        )
    return PROVIDERS[provider_id]
