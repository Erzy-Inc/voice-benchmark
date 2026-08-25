"""voicebench CLI.

    voicebench run --track stt --provider deepgram-nova-3 --dataset core-en-synth-v1
    voicebench run --track stt --all
    voicebench report
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from .providers import PROVIDERS
from .reporting import build_report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="voicebench")
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="Run benchmark providers over a dataset")
    run.add_argument("--track", choices=["stt", "e2e"], default="stt")
    run.add_argument("--provider", action="append", default=[])
    run.add_argument("--all", action="store_true", help="every configured provider")
    run.add_argument("--dataset", default="core-en-synth-v1")

    rep = sub.add_parser("report", help="Rebuild leaderboard tables + site from results/")
    rep.add_argument("--format", choices=["md", "json"], default="md")

    args = p.parse_args(argv)

    if args.cmd == "run":
        from .runner import run_provider

        ids = (
            [pid for pid, prov in PROVIDERS.items() if prov.is_configured()]
            if args.all
            else args.provider
        )
        if not ids:
            print("no providers selected (use --provider or --all)", file=sys.stderr)
            return 2
        for pid in ids:
            provider = PROVIDERS[pid]
            if not provider.is_configured():
                print(f"skip {pid}: missing {provider.required_env}", file=sys.stderr)
                continue
            print(f"▶ running {pid} on {args.dataset} ...")
            result = asyncio.run(run_provider(provider, args.dataset, track=args.track))
            print(f"  summary: {result['summary']}")
            print(f"  saved:   {result['results_file']}")
        return 0

    if args.cmd == "report":
        out = build_report()
        print(out)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
