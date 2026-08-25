# Contributing

Thanks for helping make voice-benchmark the reference open benchmark for
realtime speech AI.

## Adding a provider

1. Read `src/voicebench/providers/base.py` and `providers/README.md`.
2. Implement `BaseProvider` — forward bytes, timestamp events at receive time,
   declare your cost source.
3. Register it in `src/voicebench/providers/__init__.py`.
4. Add the API key name to `.env.example` and the workflow env block.
5. PRs must pass: `pytest -q`, `ruff check .`, `mypy src`.

Rules: no faked timings, no normalization tuned to favor your vendor, and any
turn-decision behavior your endpoint has stays visible in the results.

## Adding a dataset

See `datasets/README.md`. Datasets are immutable once referenced by any
committed result — ship `*-v2`, don't patch `*-v1`.

## Local development

```bash
pip install -e ".[dev]"
python -m voicebench.seed          # synthetic fixture set
pytest -q                          # offline tests, no keys needed
voicebench run --provider echo-stub --dataset core-en-synth-v1   # smoke path
```

## Reporting vendor regressions

Open an issue with the run artifact (results/*.json) attached. Numbers move;
what we care about is *why* — model swap, routing change, regional endpoint.
