# voice-benchmark

Open-source, fully automated benchmarks for realtime speech AI — from streaming
STT alone to complete STT → LLM → TTS agent loops.

Inspired by [benchmarks.speko.ai](https://benchmarks.speko.ai/). Every number on
the leaderboard is produced end-to-end by CI: a GitHub Actions run executes the
harness against real vendor endpoints, writes versioned JSON results, regenerates
markdown tables and a static leaderboard site, and publishes them via GitHub
Pages. No hand-edited numbers.

## What we measure

### Realtime STT track

| Metric | Definition |
| --- | --- |
| **WER** | Word error rate of finalized transcripts vs reference (Sclite-style scoring, jiwer) |
| **Finalize latency** | Time from caller silence to finalized transcript — p50 / p90 |
| **Time to first token (TTFT)** | Time from audio start to first transcript token — p50 / p90 |
| **Cost** | Vendor's published streaming rate per 1k minutes |

### Voice-agent E2E track

Full loop latency: user stops speaking → agent audio starts playing back.
Decomposed into STT finalize + LLM first token + TTS time-to-first-audio.

## Vendors

Realtime STT: AssemblyAI · ElevenLabs Scribe v2 Realtime · Deepgram Nova-3 /
Flux · OpenAI GPT-4o Transcribe (realtime) · Soniox · Cartesia Ink-2 · Google
Chirp 3 · Gladia · Inworld · Smallest AI Pulse · xAI Grok STT · Alibaba Qwen3-ASR

E2E: any combination of an STT adapter, an LLM (Anthropic / OpenAI), and a TTS
adapter.

## Quickstart

```bash
pip install -e ".[dev]"
cp .env.example .env.local && set -a; source .env.local; set +a  # paste vendor keys

# run every enabled provider on the default dataset
voicebench run --track stt --all

# one provider
voicebench run --track stt --provider deepgram-nova-3

# E2E loop benchmark
voicebench run --track e2e --stt deepgram-nova-3 --llm claude-sonnet --tts elevenlabs

# regenerate leaderboard + site from stored results
voicebench report
```

TypeScript SDK:

```bash
npm install
npx tsx src/ts/run.ts --track stt --provider soniox-stt-rt-v5
```

## Repository layout

```
datasets/           manifest + audio + references (see datasets/README.md)
providers/          one adapter per vendor — implement BaseProvider to add yours
src/voicebench/     Python harness: runner, metrics, timing, reporting, CLI
src/ts/             TypeScript SDK mirroring the Python adapters
results/            committed JSON per run (versioned, append-only)
site/               leaderboard generator -> GitHub Pages output
.github/workflows/  nightly + manual benchmark runs; auto-publishes the site
CONTRIBUTING.md     how to add a provider or dataset
docs/METHODOLOGY.md scoring definitions, normalization rules, caveats
```

## Methodology

See [docs/METHODOLOGY.md](docs/METHODOLOGY.md). Short version:

1. Fixed, versioned audio fixtures with human-verified references.
2. Streaming over each vendor's realtime websocket with realistic chunking
   (20–100 ms frames), timestamps recorded client-side at send/receive.
3. Finalized text normalized identically for hypothesis and reference before WER.
4. Latency percentiles computed over all turns; runs are re-executed nightly so
   numbers reflect current vendor behaviour, not a one-time snapshot.

## Adding a provider

Implement `BaseProvider` (`connect`, `stream_audio`, `finalize`, `close`) and a
small YAML descriptor; see `providers/README.md` and any existing adapter. The
runner, metrics, and leaderboard pick it up automatically.

## License

MIT — see [LICENSE](LICENSE).
