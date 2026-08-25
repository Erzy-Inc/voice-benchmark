# Methodology

How voice-benchmark produces every number. The design goals: **comparable**
(identical rules for all providers), **reproducible** (versioned fixtures +
committed raw results), and **honest** (vendor quirks stay visible).

## Tracks

### Realtime STT

Audio is streamed over each vendor's realtime websocket at real-time pace in
40 ms frames of 16 kHz mono PCM. All timestamps are taken client-side with a
monotonic clock (`time.monotonic()`), at the moment bytes cross the socket.

| Metric | Definition |
| --- | --- |
| **TTFT** (time to first token) | `t(first partial containing non-empty text) − t(audio start)` |
| **Finalize latency** | `t(final transcript after utterance end) − t(last audio byte sent)`. This is the number that gates the agent's reply, not the first partial. |
| **WER** | Word error rate of the concatenated final transcript vs the human reference |
| **Cost** | Vendor's published streaming rate per 1k minutes; source linked in each adapter |

Latencies are reported as p50 and p90 across all turns of all recent runs.

### Voice-agent E2E

Full loop: user stops speaking → agent audio starts.

```
e2e_total = stt_finalize + llm_first_token + tts_first_audio
```

Each leg is measured independently so regressions localize to a component.

## Text normalization

Applied identically to reference and hypothesis before WER:

1. NFKC unicode normalization, lowercasing.
2. Contraction expansion (fixed list — see `metrics.py`).
3. Punctuation removal; `$` and `%` retained.
4. Whitespace collapse.

We deliberately do **not** apply inverse-text-normalization stripping by
default: vendors that spell out numbers score as errors, and that is a real
cost for downstream agents. Slice analysis by tag (`numbers`, `short`, …)
surfaces *why* a provider scores as it does rather than hiding it.

## Datasets

- Fixtures are immutable once referenced by any committed result; changes ship
  as `*-v2`.
- CI runs on a deterministic synthetic set so the pipeline is exercised without
  third-party audio. Synthetic-set WER measures pipeline consistency, not
  vendor accuracy — accuracy numbers require the recorded sets, added
  out-of-band with documented provenance and consent.
- Every committed result cites `dataset_id` + repo git SHA + harness version.

## Honesty rules

1. No forced finalize where the vendor owns turn decisions — we measure what
   production traffic experiences.
2. Raw per-turn records are committed under `results/`; leaderboard aggregates
   are always derivable from them.
3. Provider annotations (e.g. "finalizes eagerly", "regional endpoint") are part
   of the result presentation, not buried in footnotes.
4. Runs re-execute nightly: numbers reflect current vendor behaviour, never a
   one-time snapshot.

## Threats to validity / known caveats

- Client-side timing includes network RTT from the runner region
  (`us-east` GitHub runners today). Cross-provider comparison is fair;
  absolute values shift with geography.
- Vendor endpoints may route differently over time; nightly runs surface this,
  and annotated runs record anomalies.
- Synthetic audio lacks telephony channel effects (8 kHz codecs, noise).
  A `telephony-en-v1` set with 8 kHz µ-law transcoding is planned.
