"""Soniox stt-rt-v5 adapter.

Protocol (public docs, Aug 2026):
- wss://stt-rt.soniox.com/transcribe-websocket
- First message: JSON config {api_key, model, audio_format, sample_rate,
  num_channels, enable_endpoint_detection}.
- Then raw binary audio frames; responses are JSON with
  ``tokens: [{text, is_final}]`` and a terminal ``finished`` flag.
- Endpoint detection owns turn finalization — measured as production sees it.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator

from .base import BaseProvider, TranscriptEvent

SONIOX_WS = "wss://stt-rt.soniox.com/transcribe-websocket"


class SonioxSTTRTV5(BaseProvider):
    provider_id = "soniox-stt-rt-v5"
    display_name = "Soniox stt-rt-v5"
    # TODO(cost): confirm published streaming rate; withheld until verified.
    required_env = ["SONIOX_API_KEY"]

    async def connect(self) -> None:
        import websockets

        self._events: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._ws = await websockets.connect(SONIOX_WS, max_size=None)
        await self._ws.send(
            json.dumps(
                {
                    "api_key": os.environ["SONIOX_API_KEY"],
                    "model": "stt-rt-v5",
                    "audio_format": "pcm_s16le",
                    "sample_rate": 16000,
                    "num_channels": 1,
                    "language_hints": ["en"],
                    "enable_endpoint_detection": True,
                }
            )
        )
        self._recv_task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if msg.get("error_code") is not None:
                    # surface vendor errors in results rather than hiding them
                    self._events.put_nowait(
                        TranscriptEvent.now(
                            "final", f"[error {msg['error_code']}] {msg.get('error_message', '')}"
                        )
                    )
                    break
                finals = [
                    t.get("text", "")
                    for t in msg.get("tokens", [])
                    if t.get("is_final") and t.get("text")
                ]
                if finals:
                    self._events.put_nowait(TranscriptEvent.now("final", " ".join(finals)))
                if msg.get("finished"):
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
        # Empty text frame signals end-of-audio; endpoint detection then
        # flushes all remaining non-final tokens as final.
        await self._ws.send("")
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
