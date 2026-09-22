"""Command-line entry: py -m trendfinder run --week 2026-W39 --mode stub"""

import argparse
import logging
from pathlib import Path

import anthropic

from .config import Settings, week_id
from .db import Database
from .llm import LLMClient
from .pipeline import Stages, run_week
from .teams.stubs import StubAnalyze, StubCollect, StubCurate, StubReport


def build_stages(settings: Settings, mode: str) -> Stages:
    if mode == "stub":
        return Stages(
            collect=StubCollect(settings.fixtures_dir / "raw_signals.json"),
            curate=StubCurate(settings.fixtures_dir / "candidates.json"),
            analyze=StubAnalyze(),
            report=StubReport(),
        )
    raise NotImplementedError("live stages arrive in plan 2")


def _settings_from_args(args: argparse.Namespace) -> Settings:
    s = Settings.from_env()
    over = {}
    if args.db:
        over["db_path"] = Path(args.db)
    if args.reports_dir:
        over["reports_dir"] = Path(args.reports_dir)
    if args.fixtures_dir:
        over["fixtures_dir"] = Path(args.fixtures_dir)
    return s.model_copy(update=over)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="trendfinder")
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run one weekly pipeline")
    run.add_argument("--week", default=None, help="ISO week id, e.g. 2026-W39 (default: this week)")
    run.add_argument("--mode", choices=["stub", "live"], default="live")
    run.add_argument("--db", default=None)
    run.add_argument("--reports-dir", default=None)
    run.add_argument("--fixtures-dir", default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = _settings_from_args(args)
    stages = build_stages(settings, args.mode)
    week = args.week or week_id()

    client = anthropic.Anthropic() if args.mode == "live" else None
    llm = LLMClient(client, settings)
    with Database(settings.db_path) as db:
        db.init_schema()
        outcome = run_week(week, stages, db, llm, settings)

    print(f"{outcome.week} {outcome.status} cost=${outcome.cost_usd:.2f} report={outcome.report_path}")
    for w in outcome.warnings:
        print(f"  warning: {w}")
    return 0 if outcome.status == "ok" else 1
