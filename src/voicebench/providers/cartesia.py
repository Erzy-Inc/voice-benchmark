"""Cartesia Ink streaming STT adapter.

Protocol (public docs, Aug 2026):
- wss://api.cartesia.ai/stt/websocket?... (query bindings: model, language,
  encoding, sample_rate)
- Auth: ``X-API-Key`` header.
- Binary frames carry raw audio; text frames are control commands:
  ``finalize`` -> flush buffered audio + transcript chunks, then
  ``flush_done``; ``close`` -> session end + ``done``.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator

from .base import BaseProvider, TranscriptEvent

CARTESIA_WS = (
    "wss://api.cartesia.ai/stt/websocket"
    "?model=ink-whisper&language=en&encoding=pcm_s16le&sample_rate=16000"
)


class CartesiaInk(BaseProvider):
    provider_id = "cartesia-ink"
    display_name = "Cartesia Ink"
    # TODO(cost): confirm published streaming rate; withheld until verified.
    required_env = ["CARTESIA_API_KEY"]

    async def connect(self) -> None:
        import websockets

        self._events: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._ws = await websockets.connect(
            CARTESIA_WS,
            additional_headers={
                "X-API-Key": os.environ["CARTESIA_API_KEY"],
                "Cartesia-Version": "2026-08-14",
            },
            max_size=None,
        )
        self._recv_task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        try:
            async for raw in self._ws:
                if isinstance(raw, bytes):
                    continue  # binary frames aren't part of the STT downlink
                msg = json.loads(raw)
                mtype = msg.get("type")
                if mtype == "transcript":
                    if msg.get("text"):
                        kind = "final" if msg.get("is_final") else "partial"
                        self._events.put_nowait(
                            TranscriptEvent.now(kind, msg["text"])
                        )
                elif mtype == "flush_done":
                    break
                elif mtype == "error":
                    self._events.put_nowait(
                        TranscriptEvent.now("final", f"[error] {msg.get('message', '')}")
                    )
                    break
        except Exception:
            pass
        finally:
            self._events.put_nowait(None)

    async def stream_audio(self, chunk: bytes) -> AsyncIterator[TranscriptEvent]:
        await self._ws.send(chunk)
        return
        yield  # pragma: no cover

    async def finalize(self) -> AsyncIterator[TranscriptEvent]:
        await self._ws.send("finalize")
        while True:
            ev = await self._events.get()
            if ev is None:
                return
            yield ev

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self._ws.send("close")
            if hasattr(self, "_recv_task"):
                self._recv_task.cancel()
            if hasattr(self, "_ws"):
                await self._ws.close()
