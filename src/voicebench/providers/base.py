"""Provider contract.

To add a vendor, subclass BaseProvider and register it in providers/__init__.py.
See providers/README.md for the walkthrough.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass
class TranscriptEvent:
    kind: str  # "partial" | "final"
    text: str
    t_ms: float

    @classmethod
    def now(cls, kind: str, text: str) -> TranscriptEvent:
        from ..timing import now_ms

        return cls(kind=kind, text=text, t_ms=now_ms())


class BaseProvider(ABC):
    """A realtime STT endpoint streamed audio over a websocket."""

    provider_id: str = "base"
    display_name: str = "Base"
    cost_per_1k_min_usd: float | None = None  # published streaming rate
    required_env: list[str] = []

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    def stream_audio(self, chunk: bytes) -> AsyncIterator[TranscriptEvent]:
        """Yield transcript events produced while this chunk is being processed."""
        ...

    @abstractmethod
    def finalize(self) -> AsyncIterator[TranscriptEvent]:
        """Drain events after the utterance ends; must yield the final transcript."""
        ...

    @abstractmethod
    async def close(self) -> None: ...

    def is_configured(self) -> bool:
        import os

        return all(os.getenv(k) for k in self.required_env)
