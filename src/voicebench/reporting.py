"""Report generation: results/*.json -> leaderboard markdown + static site data."""
from __future__ import annotations

import json
from pathlib import Path

from .timing import RunRecord, percentile

RESULTS_DIR = Path(__file__).resolve().parents[2] / "results"
SITE_DIR = Path(__file__).resolve().parents[2] / "site"


def load_all_results() -> list[RunRecord]:
    records: list[RunRecord] = []
    if not RESULTS_DIR.exists():
        return records
    for path in sorted(RESULTS_DIR.glob("*.json")):
        try:
            d = json.loads(path.read_text())
            rec = RunRecord(
                provider_id=d["provider_id"],
                dataset_id=d["dataset_id"],
                track=d.get("track", "stt"),
                started_at_utc=d["started_at_utc"],
                harness_version=d.get("harness_version", "?"),
                dataset_git_sha=d.get("dataset_git_sha", "unknown"),
                turns=d.get("turns", []),
            )
            records.append(rec)
        except Exception as e:  # corrupt result files must not kill the report
            print(f"warn: skipping {path.name}: {e}")
    return records


def aggregate(records: list[RunRecord]) -> list[dict]:
    by_provider: dict[str, list[RunRecord]] = {}
    for r in records:
        if r.provider_id == "echo-stub":
            continue  # offline stub never ranks
        by_provider.setdefault(r.provider_id, []).append(r)

    rows = []
    for pid, recs in sorted(by_provider.items()):
        wers = [t["wer"] for r in recs for t in r.turns if t.get("wer") is not None]
        ttfts = [t["ttft_ms"] for r in recs for t in r.turns if t.get("ttft_ms") is not None]
        finals = [t["finalize_ms"] for r in recs for t in r.turns if t.get("finalize_ms") is not None]
        cost = _cost_for(pid)
        rows.append(
            {
                "provider_id": pid,
                "wer": round(100 * (sum(wers) / len(wers)), 2) if wers else None,
                "finalize_p50_ms": percentile(finals, 50),
                "finalize_p90_ms": percentile(finals, 90),
                "ttft_p50_ms": percentile(ttfts, 50),
                "ttft_p90_ms": percentile(ttfts, 90),
                "cost_per_1k_min_usd": cost,
                "runs": len(recs),
                "n_turns": sum(len(r.turns) for r in recs),
            }
        )
    rows.sort(key=lambda x: (x["wer"] is None, x["wer"] or 99))
    return rows


def _cost_for(provider_id: str) -> float | None:
    from .providers import PROVIDERS

    p = PROVIDERS.get(provider_id)
    return getattr(p, "cost_per_1k_min_usd", None) if p else None


def leaderboard_md(rows: list[dict], dataset_id: str) -> str:
    lines = [
        f"# Leaderboard — {dataset_id}",
        "",
        "| Provider | WER ↓ | Finalize p50 | Finalize p90 | TTFT p50 | TTFT p90 | Cost/1k min |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        fmt = lambda v, suf="": f"{v}{suf}" if v is not None else "—"
        lines.append(
            f"| {r['provider_id']} | {fmt(r['wer'], '%')} "
            f"| {fmt(r['finalize_p50_ms'], 'ms')} | {fmt(r['finalize_p90_ms'], 'ms')} "
            f"| {fmt(r['ttft_p50_ms'], 'ms')} | {fmt(r['ttft_p90_ms'], 'ms')} "
            f"| {('$%.2f' % r['cost_per_1k_min_usd']) if r['cost_per_1k_min_usd'] else '—'} |"
        )
    lines += [
        "",
        f"_Auto-generated from results/ — do not edit. Runs: {sum(r['runs'] for r in rows)}._",
        "",
    ]
    return "\n".join(lines)


def build_report() -> str:
    records = load_all_results()
    dataset = records[0].dataset_id if records else "core-en-synth-v1"
    rows = aggregate(records)

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "data" / "leaderboard.json").parent.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "data" / "leaderboard.json").write_text(json.dumps(rows, indent=2))

    md = leaderboard_md(rows, dataset)
    (Path("LEADERBOARD.md")).write_text(md)
    return md
