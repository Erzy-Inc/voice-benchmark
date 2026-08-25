"""Deepgram Nova-3 realtime adapter + offline EchoProvider stub."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator

from .base import BaseProvider, TranscriptEvent

DEEPGRAM_WS = (
    "wss://api.deepgram.com/v1/listen"
    "?encoding=linear16&sample_rate=16000&channels=1&punctuate=true"
)


class DeepgramNova3(BaseProvider):
    """Deepgram Nova-3 streaming.

    Cost source: https://deepgram.com/pricing (streaming rate re-verified
    monthly by CI).
    """

    provider_id = "deepgram-nova-3"
    display_name = "Deepgram Nova-3"
    cost_per_1k_min_usd = 4.30  # streaming tier, published rate
    required_env = ["DEEPGRAM_API_KEY"]

    async def connect(self) -> None:
        import websockets

        key = os.environ["DEEPGRAM_API_KEY"]
        self._ws = await websockets.connect(
            DEEPGRAM_WS, additional_headers={"Authorization": f"Token {key}"}
        )
        self._events: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._recv_task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                alt = msg.get("channel", {}).get("alternatives", [{}])[0].get(
                    "transcript", ""
                )
                if not alt:
                    continue
                kind = (
                    "final"
                    if msg.get("speech_final") or msg.get("is_final")
                    else "partial"
                )
                self._events.put_nowait(TranscriptEvent.now(kind, alt))
        except Exception:
            pass
        finally:
            self._events.put_nowait(None)

    async def stream_audio(self, chunk: bytes) -> AsyncIterator[TranscriptEvent]:
        await self._ws.send(chunk)
        return
        yield  # pragma: no cover — events arrive via the receive pump

    async def finalize(self) -> AsyncIterator[TranscriptEvent]:
        await self._ws.send(json.dumps({"type": "Finalize"}))
        while True:
            ev = await self._events.get()
            if ev is None:
                return
            yield ev

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            if hasattr(self, "_recv_task"):
                self._recv_task.cancel()
            if hasattr(self, "_ws"):
                await self._ws.close()


class EchoProvider(BaseProvider):
    """Deterministic offline stub: returns a preset text as its transcript.

    Used by tests and the CI smoke job so the full harness path runs without any
    API keys. Never appears on the leaderboard.
    """

    provider_id = "echo-stub"
    display_name = "Echo Stub (offline)"
    required_env: list[str] = []

    def __init__(self) -> None:
        self._pending_text = ""

    def set_reference(self, text: str) -> None:
        self._pending_text = text

    async def connect(self) -> None:
        pass

    async def stream_audio(self, chunk: bytes) -> AsyncIterator[TranscriptEvent]:
        return
        yield  # pragma: no cover

    async def finalize(self) -> AsyncIterator[TranscriptEvent]:
        yield TranscriptEvent.now("final", self._pending_text)

    async def close(self) -> None:
        pass
