"""AssemblyAI Universal-3.5 Pro streaming adapter.

Protocol (public docs, Aug 2026):
- wss://api.assemblyai.com/v3/stream?sample_rate=16000&speech_model=universal-3-5-pro
- Auth: ``Authorization: <key>`` header
- Binary frames carry audio; JSON frames carry events.
- Turn events carry ``end_of_turn``; termination via ``{"type": "Terminate"}``.
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator

from .base import BaseProvider, TranscriptEvent

STREAM_URL = (
    "wss://streaming.assemblyai.com/v3/ws"
    "?sample_rate=16000&speech_model=universal-3-5-pro"
)


class AssemblyAIUniversal35Pro(BaseProvider):
    provider_id = "assemblyai-universal-3-5-pro"
    display_name = "AssemblyAI Universal-3.5 Pro"
    # TODO(cost): confirm published streaming rate; withheld until verified.
    required_env = ["ASSEMBLYAI_API_KEY"]

    async def connect(self) -> None:
        import websockets

        self._events: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._ws = await websockets.connect(
            STREAM_URL,
            additional_headers={
                "Authorization": os.environ["ASSEMBLYAI_API_KEY"],
            },
            max_size=None,
        )
        self._recv_task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                mtype = msg.get("type")
                if mtype == "Turn":
                    text = msg.get("transcript", "")
                    if not text:
                        continue
                    kind = "final" if msg.get("end_of_turn") else "partial"
                    self._events.put_nowait(TranscriptEvent.now(kind, text))
                elif mtype == "Termination":
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
        await self._ws.send(json.dumps({"type": "Terminate"}))
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
