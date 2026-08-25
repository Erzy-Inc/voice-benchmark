"""Registry of benchmark providers.

Each module exports PROVIDERS: list[BaseProvider] instances. Adding a vendor =
new module + one line below. See providers/README.md.
"""
from __future__ import annotations

from .base import BaseProvider
from .deepgram import DeepgramNova3, EchoProvider

PROVIDERS: dict[str, BaseProvider] = {
    p.provider_id: p for p in [EchoProvider(), DeepgramNova3()]
}

__all__ = ["PROVIDERS", "BaseProvider"]


def get_provider(provider_id: str) -> BaseProvider:
    if provider_id not in PROVIDERS:
        raise KeyError(
            f"unknown provider '{provider_id}'. Registered: {sorted(PROVIDERS)}"
        )
    return PROVIDERS[provider_id]
