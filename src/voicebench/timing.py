"""Timing utilities for latency measurement.

All timestamps are taken client-side with a monotonic clock at the moment bytes
are handed to / received from the socket, so every provider is measured under
identical rules.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


def now_ms() -> float:
    return time.monotonic() * 1000.0


@dataclass
class TurnTimings:
    """Client-side timing record for a single utterance streamed to a provider."""

    turn_id: str
    t_audio_start_ms: float | None = None
    t_first_token_ms: float | None = None
    t_silence_start_ms: float | None = None
    t_finalized_ms: float | None = None

    @property
    def ttft_ms(self) -> float | None:
        if self.t_first_token_ms is None or self.t_audio_start_ms is None:
            return None
        return self.t_first_token_ms - self.t_audio_start_ms

    @property
    def finalize_ms(self) -> float | None:
        if self.t_finalized_ms is None or self.t_silence_start_ms is None:
            return None
        return self.t_finalized_ms - self.t_silence_start_ms


@dataclass
class RunRecord:
    """One complete run of one provider over one dataset."""

    provider_id: str
    dataset_id: str
    track: str
    started_at_utc: str
    harness_version: str
    dataset_git_sha: str
    turns: list[dict[str, Any]] = field(default_factory=list)

    def add_turn(self, **kwargs: Any) -> None:
        self.turns.append(kwargs)


def percentile(values: list[float], q: float) -> float | None:
    """Linear-interpolated percentile; None on empty input."""
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * (q / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return round(s[f] + (s[c] - s[f]) * (k - f), 2)


def summarize(records: list[RunRecord]) -> dict[str, Any]:
    """Aggregate per-turn records into leaderboard metrics."""
    ttfts = [t["ttft_ms"] for r in records for t in r.turns if t.get("ttft_ms") is not None]
    finals = [t["finalize_ms"] for r in records for t in r.turns if t.get("finalize_ms") is not None]
    return {
        "ttft_p50_ms": percentile(ttfts, 50),
        "ttft_p90_ms": percentile(finals, 90),
        "finalize_p50_ms": percentile(finals, 50),
        "finalize_p90_ms": percentile(finals, 90),
        "n_turns": sum(len(r.turns) for r in records),
    }
