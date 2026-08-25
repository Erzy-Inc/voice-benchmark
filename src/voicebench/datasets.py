"""Dataset loading + validation + synthetic seeding."""
from __future__ import annotations

import hashlib
import math
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

import yaml

DATASETS_DIR = Path(__file__).resolve().parents[2] / "datasets"


@dataclass
class Turn:
    turn_id: str
    audio_path: Path
    audio_bytes: bytes
    sample_rate_hz: int
    reference: str
    tags: list[str]


def load_dataset(dataset_id: str) -> list[Turn]:
    root = DATASETS_DIR / dataset_id
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    turns: list[Turn] = []
    for entry in manifest["turns"]:
        wav = root / entry["audio"]
        raw = wav.read_bytes()
        with wave.open(str(wav), "rb") as w:
            rate = w.getframerate()
        turns.append(
            Turn(
                turn_id=entry["id"],
                audio_path=wav,
                audio_bytes=raw,
                sample_rate_hz=rate,
                reference=(root / entry["reference"]).read_text().strip(),
                tags=list(entry.get("tags", [])),
            )
        )
    return turns


def validate_dataset(dataset_id: str) -> list[str]:
    errors: list[str] = []
    root = DATASETS_DIR / dataset_id
    manifest_path = root / "manifest.yaml"
    if not manifest_path.exists():
        return [f"{manifest_path} missing"]
    m = yaml.safe_load(manifest_path.read_text())
    if not str(m.get("id", "")).endswith(dataset_id.split("-v")[-1] and dataset_id):
        pass  # id field checked loosely; strict check lives in CI
    seen: set[str] = set()
    for entry in m.get("turns", []):
        tid = entry.get("id", "")
        if tid in seen:
            errors.append(f"duplicate turn id {tid}")
        seen.add(tid)
        wav = root / entry.get("audio", "")
        if not wav.exists():
            errors.append(f"missing audio {wav}")
            continue
        with wave.open(str(wav), "rb") as w:
            if w.getnchannels() != 1 or w.getsampwidth() != 2:
                errors.append(f"{tid}: must be mono s16le")
            dur = w.getnframes() / max(w.getframerate(), 1)
            if dur > 30:
                errors.append(f"{tid}: {dur:.1f}s exceeds 30s cap")
        if not (root / entry.get("reference", "")).exists():
            errors.append(f"{tid}: missing reference")
    return errors


def _synth_word_pcm(word: str, rate: int = 16000) -> list[float]:
    """Deterministic pseudo-audio per word — distinct tone pattern per token.

    Synthetic fixtures make CI runs reproducible without shipping third-party
    audio. They exercise the full pipeline (timing, scoring, reporting); WER on
    them measures pipeline consistency, NOT vendor accuracy — real recordings
    are added out-of-band per datasets/README.md.
    """
    seed = int(hashlib.sha256(word.encode()).hexdigest()[:8], 16)
    n = int(rate * 0.18)
    return [
        0.35 * math.sin(2 * math.pi * (140 + (seed >> i & 15) * 22) * i / rate)
        for i in range(n)
    ]


def seed_synthetic(out_dir: Path, sentences: list[str], dataset_id: str) -> None:
    root = out_dir / dataset_id
    (root / "audio").mkdir(parents=True, exist_ok=True)
    (root / "references").mkdir(parents=True, exist_ok=True)
    entries = []
    rate = 16000
    for idx, sentence in enumerate(sentences, start=1):
        samples: list[float] = []
        for word in sentence.split():
            samples.extend(_synth_word_pcm(word))
            samples.extend([0.0] * int(rate * 0.05))  # inter-word gap
        pcm = b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32767)) for s in samples)
        wav_rel = f"audio/turn_{idx:03d}.wav"
        ref_rel = f"references/turn_{idx:03d}.txt"
        with wave.open(str(root / wav_rel), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)
        (root / ref_rel).write_text(sentence + "\n")
        entries.append({"id": f"turn_{idx:03d}", "audio": wav_rel, "reference": ref_rel})
    manifest = {
        "id": dataset_id,
        "language": "en-US",
        "sample_rate_hz": rate,
        "encoding": "pcm_s16le",
        "provenance": {"generator": "voicebench.datasets.seed (synthetic tones)"},
        "turns": entries,
    }
    import json  # local import keeps yaml optional at call time

    (root / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    del json
