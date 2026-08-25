"""Core benchmark runner: dataset -> provider stream -> timings + transcript -> score."""
from __future__ import annotations

import asyncio
import contextlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from .datasets import DATASETS_DIR, Turn, load_dataset
from .metrics import wer
from .providers.base import BaseProvider, TranscriptEvent
from .timing import RunRecord, now_ms

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"

# Realistic streaming cadence: 40ms of 16kHz mono s16le audio per chunk.
CHUNK_MS = 40
SAMPLE_RATE = 16000
BYTES_PER_MS = SAMPLE_RATE * 2 / 1000


async def run_turn(provider: BaseProvider, turn: Turn, record: RunRecord) -> dict:
    await provider.connect()
    t_audio_start = now_ms()

    final_text = ""
    t_first_token: float | None = None
    queue: asyncio.Queue[TranscriptEvent | None] = asyncio.Queue()

    async def pump(gen):
        async for ev in gen:
            queue.put_nowait(ev)
        queue.put_nowait(None)

    # Feed chunks at real-time pace so vendors see a realistic stream.
    pos = 0
    audio = turn.audio_bytes
    header = 44 if audio[:4] == b"RIFF" else 0
    pcm = audio[header:]
    chunk_size = int(BYTES_PER_MS * CHUNK_MS)

    async def feeder():
        nonlocal pos
        while pos < len(pcm):
            chunk = pcm[pos : pos + chunk_size]
            pos += len(chunk)
            with contextlib.suppress(Exception):
                async for _ in provider.stream_audio(chunk):
                    pass
            await asyncio.sleep(CHUNK_MS / 1000)
        t_silence = now_ms()
        async for ev in provider.finalize():
            queue.put_nowait(ev)
        queue.put_nowait(("__silence__", t_silence))  # type: ignore[assignment]
        queue.put_nowait(None)  # end-of-turn sentinel

    feed_task = asyncio.create_task(feeder())

    t_finalized: float | None = None
    t_silence: float | None = None
    while True:
        ev = await queue.get()
        if ev is None:
            break
        if isinstance(ev, tuple):  # silence marker from feeder
            _, t_silence = ev
            continue
        if ev.kind == "final":
            if t_finalized is None:
                t_finalized = ev.t_ms
            final_text += (" " if final_text else "") + ev.text
        elif t_first_token is None and ev.text.strip():
            t_first_token = ev.t_ms

    await feed_task
    await provider.close()

    ttft = (t_first_token - t_audio_start) if t_first_token else None
    fin = (t_finalized - t_silence) if (t_finalized and t_silence) else None
    row = {
        "turn_id": turn.turn_id,
        "reference": turn.reference,
        "transcript": final_text,
        "wer": wer(turn.reference, final_text),
        "ttft_ms": round(ttft, 2) if ttft else None,
        "finalize_ms": round(fin, 2) if fin else None,
        "tags": turn.tags,
    }
    record.add_turn(**row)
    return row


def git_sha(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=path, text=True
        ).strip()[:12]
    except Exception:
        return "unknown"


def persist(record: RunRecord) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = record.started_at_utc.replace(":", "").replace("-", "")
    out = RESULTS_DIR / f"{record.provider_id}--{record.dataset_id}--{stamp}.json"
    out.write_text(json.dumps(record.__dict__, indent=2))
    return out


async def run_provider(provider: BaseProvider, dataset_id: str, track: str = "stt") -> dict:
    record = RunRecord(
        provider_id=provider.provider_id,
        dataset_id=dataset_id,
        track=track,
        started_at_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        harness_version="0.1.0",
        dataset_git_sha=git_sha(DATASETS_DIR),
    )
    turns = load_dataset(dataset_id)
    for turn in turns:
        await run_turn(provider, turn, record)
        await asyncio.sleep(0.3)  # cooldown between turns
    path = persist(record)
    from .timing import summarize

    summary = summarize([record])
    return {"summary": summary, "results_file": str(path)}
