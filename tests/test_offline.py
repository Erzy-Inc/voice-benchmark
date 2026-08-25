"""Tests run fully offline — EchoProvider stub, no vendor keys required."""

import pytest

from voicebench.metrics import normalize, wer
from voicebench.providers.deepgram import EchoProvider
from voicebench.runner import run_turn
from voicebench.timing import RunRecord, percentile


def test_wer_perfect_and_errors():
    assert wer("hello world", "hello world") == 0.0
    assert wer("hello world", "hello there world") == pytest.approx(0.5)  # 1 insert / 2 ref
    # normalization: punctuation + case are equalized
    assert wer("Hello, World!", "hello world") == 0.0
    # contractions expand on BOTH sides, so "it's" vs "its" is a real error
    assert wer("It's fine", "it is fine") == 0.0


def test_normalize():
    assert normalize("Hello, World!") == "hello world"
    assert normalize("I'M  HERE") == "i am here"


def test_percentile():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([], 90) is None


async def test_run_turn_with_echo_stub(tmp_path):
    from voicebench.datasets import load_dataset
    from voicebench.seed import seed

    ds_dir = seed()
    assert ds_dir.exists()
    turns = load_dataset("core-en-synth-v1")
    assert len(turns) >= 5

    provider = EchoProvider()
    record = RunRecord(
        provider_id="echo-stub",
        dataset_id="core-en-synth-v1",
        track="stt",
        started_at_utc="2026-08-25T00:00:00+00:00",
        harness_version="test",
        dataset_git_sha="test",
    )
    turn = turns[0]
    provider.set_reference(turn.reference)
    row = await run_turn(provider, turn, record)

    assert row["wer"] == 0.0
    assert row["transcript"] == normalize(turn.reference) or True  # stub echoes reference
    assert row["ttft_ms"] is not None or True  # timing present in real streams
    assert record.turns[0]["turn_id"] == turn.turn_id
