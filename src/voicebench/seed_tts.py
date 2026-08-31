"""Generate core-en-tts-v1: real-speech fixtures synthesized via ElevenLabs TTS.

The synthetic tone set exercises the pipeline but yields no meaningful WER
(vendors correctly return nothing for sine patterns). This set uses TTS speech
so vendor accuracy becomes measurable. References are the input sentences;
provenance records generator + voice so the set stays reproducible.
"""
from __future__ import annotations

import httpx
from pathlib import Path

from .datasets import DATASETS_DIR
from .seed import SENTENCES

VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel
MODEL_ID = "eleven_turbo_v2_5"
DATASET_ID = "core-en-tts-v1"


def synth(out_dir: Path | None = None) -> Path:
    import os

    import wave
    import yaml

    api_key = os.environ["ELEVENLABS_API_KEY"]
    root = (out_dir or DATASETS_DIR) / DATASET_ID
    (root / "audio").mkdir(parents=True, exist_ok=True)
    (root / "references").mkdir(parents=True, exist_ok=True)

    entries = []
    with httpx.Client(timeout=120) as client:
        for idx, sentence in enumerate(SENTENCES, start=1):
            r = client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
                params={"output_format": "pcm_16000"},
                headers={"xi-api-key": api_key},
                json={"text": sentence, "model_id": MODEL_ID},
            )
            r.raise_for_status()
            pcm = r.content
            wav_rel = f"audio/turn_{idx:03d}.wav"
            ref_rel = f"references/turn_{idx:03d}.txt"
            with wave.open(str(root / wav_rel), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(16000)
                w.writeframes(pcm)
            (root / ref_rel).write_text(sentence + "\n")
            entries.append({"id": f"turn_{idx:03d}", "audio": wav_rel,
                            "reference": ref_rel})
            print(f"  ✓ turn_{idx:03d} ({len(pcm)/32000:.1f}s)")

    manifest = {
        "id": DATASET_ID,
        "language": "en-US",
        "sample_rate_hz": 16000,
        "encoding": "pcm_s16le",
        "provenance": {
            "generator": f"ElevenLabs TTS {MODEL_ID}, voice {VOICE_ID}",
            "note": "Synthetic speech: WER comparable across vendors, but "
                    "single-speaker studio conditions — see METHODOLOGY caveats.",
        },
        "turns": entries,
    }
    (root / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    return root


if __name__ == "__main__":
    print(f"seeded: {synth()}")
