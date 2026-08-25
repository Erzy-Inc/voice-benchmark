# Datasets

Fixtures are versioned and content-addressed. A dataset is defined by
`manifest.yaml`:

```yaml
id: core-en-v1          # immutable once published; fixes go in -v2
language: en-US
sample_rate_hz: 16000
encoding: pcm_s16le
turns:
  - id: turn_001
    audio: audio/turn_001.wav      # mono PCM wav
    reference: references/turn_001.txt
    tags: [numbers, short]         # used in slice analysis
```

Rules:

1. **Immutability** — never edit audio or references after publishing a dataset
   id; results cite `dataset_id` + git SHA of this repo. Add a new version
   instead.
2. **Audio format** — mono 16 kHz PCM s16le WAV, ≤30 s per turn.
3. **References** — human-transcribed, plain text, no formatting conventions;
   normalization happens in the scorer, not here.
4. **Provenance** — synthetic TTS fixtures must record their generator in
   `provenance:`; human recordings record consent + license.
5. **CI seeding** — `python -m voicebench.datasets.seed` generates a small
   deterministic synthetic set (`core-en-synth-v1`) so CI can run without
   shipping third-party audio. Real recordings are added out-of-band and
   validated by `voicebench datasets validate`.
