"""ElevenLabs Scribe v2 Realtime adapter.

Protocol (public docs, Aug 2026):
- wss://api.elevenlabs.io/v1/speech-to-text/realtime
- Query: model_id=scribe_v2_realtime, audio_format=pcm_16000, language_code,
  commit_strategy=vad (VAD owns turn commits — measured as production sees it).
- Auth: ``xi-api-key`` header.
- Audio sent as JSON ``{"type": "input_audio_chunk", "audio_base64": ...}``;
  transcripts arrive as ``partial_transcript`` / ``committed_transcript``.
"""
from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
from collections.abc import AsyncIterator

from .base import BaseProvider, TranscriptEvent

STREAM_URL = (
    "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
    "?model_id=scribe_v2_realtime&audio_format=pcm_16000&language_code=en"
    "&commit_strategy=vad"
)

# Trailing room-tone sent during finalize so the vendor's VAD sees the caller
# stop — mirrors what production streams contain after an utterance.
TRAILING_SILENCE_CHUNKS = 14  # x 50ms = 700ms


class ElevenLabsScribeV2Realtime(BaseProvider):
    provider_id = "elevenlabs-scribe-v2-realtime"
    display_name = "ElevenLabs Scribe v2 Realtime"
    # TODO(cost): confirm published streaming rate; withheld until verified.
    required_env = ["ELEVENLABS_API_KEY"]

    async def connect(self) -> None:
        import websockets

        self._events: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()
        self._ws = await websockets.connect(
            STREAM_URL,
            additional_headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            max_size=None,
        )
        self._recv_task = asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                mtype = msg.get("type")
                if mtype == "partial_transcript":
                    if msg.get("text"):
                        self._events.put_nowait(
                            TranscriptEvent.now("partial", msg["text"])
                        )
                elif mtype in ("committed_transcript", "final_transcript"):
                    if msg.get("text"):
                        self._events.put_nowait(
                            TranscriptEvent.now("final", msg["text"])
                        )
                elif str(mtype).startswith("scribe"):
                    # auth/quota/throttle errors surface in results, never hidden
                    self._events.put_nowait(
                        TranscriptEvent.now("final", f"[{mtype}]")
                    )
        except Exception:
            pass
        finally:
            self._events.put_nowait(None)

    async def _send_b64(self, pcm: bytes) -> None:
        await self._ws.send(
            json.dumps({"type": "input_audio_chunk",
                         "audio_base64": base64.b64encode(pcm).decode()})
        )

    async def stream_audio(self, chunk: bytes) -> AsyncIterator[TranscriptEvent]:
        await self._send_b64(chunk)
        return
        yield  # pragma: no cover

    async def finalize(self) -> AsyncIterator[TranscriptEvent]:
        # Feed trailing silence so VAD-based commit fires, mirroring natural
        # post-utterance room tone in production streams.
        silence = b"\x00" * 1600  # 50ms @ 16kHz s16le mono
        for _ in range(TRAILING_SILENCE_CHUNKS):
            with contextlib.suppress(Exception):
                await self._send_b64(silence)
            await asyncio.sleep(0.05)
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
