# Providers

One directory per vendor under `src/voicebench/providers/`, registered in
`providers/__init__.py`.

## Contract

Subclass `BaseProvider` (`src/voicebench/providers/base.py`):

```python
class AcmeSTT(BaseProvider):
    provider_id = "acme-stt"
    display_name = "Acme STT"
    cost_per_1k_min_usd = 5.00      # published streaming rate
    required_env = ["ACME_API_KEY"]

    async def connect(self) -> None: ...
    def stream_audio(self, chunk: bytes) -> AsyncIterator[TranscriptEvent]: ...
    def finalize(self) -> AsyncIterator[TranscriptEvent]: ...
    async def close(self) -> None: ...
```

Rules that keep numbers comparable:

1. **No forced-finalize games.** If your vendor decides turns itself (like
   Deepgram Flux), let it — record what actually happens. The runner measures
   from client-side silence onward regardless.
2. **Timestamps come from `TranscriptEvent.now()`** at receive time. Never fake,
   smooth, or cache timings.
3. **Realistic chunking** is handled by the runner (40 ms frames). Your adapter
   only forwards bytes.
4. **Declare costs** in `cost_per_1k_min_usd` from the vendor's published page;
   link the source in the class docstring. CI re-checks these monthly.

## Reference implementations

- `deepgram.py::DeepgramNova3` — complete websocket adapter.
- `deepgram.py::EchoProvider` — offline deterministic stub used by tests + the
  CI smoke job (no API keys needed).
