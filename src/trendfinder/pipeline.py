"""Deterministic orchestrator (spec §4): runs the four teams in order, persists, writes the report."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings
from .critic import PipelineRejected, StageResult, run_with_critic
from .db import Database
from .llm import CostCapExceeded, LLMClient
from .teams.base import Stage, StageContext
from .teams.stubs import render_markdown

log = logging.getLogger(__name__)


@dataclass
class Stages:
    collect: Stage
    curate: Stage
    analyze: Stage
    report: Stage


@dataclass
class RunOutcome:
    run_id: int
    week: str
    status: str
    report_path: Path | None
    cost_usd: float
    warnings: list[str] = field(default_factory=list)


def _stage(ctx: StageContext, team: Stage, inputs: Any) -> Any:
    result: StageResult = run_with_critic(
        team.name,
        lambda issues: team.produce(ctx, inputs, issues),
        lambda out: team.critique(ctx, out),
        max_revise=ctx.settings.max_revise,
    )
    for attempt, verdict in enumerate(result.verdicts, start=1):
        ctx.db.log_critic(ctx.run_id, team.name, attempt, verdict)
    ctx.warnings.extend(result.warnings)
    return result.output


def run_week(week: str, stages: Stages, db: Database, llm: LLMClient, settings: Settings) -> RunOutcome:
    run_id = db.start_run(week)
    ctx = StageContext(run_id=run_id, week=week, db=db, llm=llm, settings=settings)
    report_path: Path | None = None
    status = "ok"
    try:
        signals = _stage(ctx, stages.collect, None)
        db.save_raw_signals(run_id, signals)

        candidates = _stage(ctx, stages.curate, signals)
        db.save_candidates(run_id, candidates)

        scored = _stage(ctx, stages.analyze, candidates)
        db.save_history(week, scored)

        cards = _stage(ctx, stages.report, scored)
        markdown = render_markdown(week, cards)
        settings.reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = settings.reports_dir / f"{week}.md"
        report_path.write_text(markdown, encoding="utf-8")
        db.save_report(run_id, markdown)
    except PipelineRejected as e:
        status = "rejected"
        ctx.warnings.append(f"{e.team} REJECT: {'; '.join(e.issues)}")
        log.error("run %s rejected by %s: %s", run_id, e.team, e.issues)
    except CostCapExceeded as e:
        status = "cost_cap"
        ctx.warnings.append(str(e))
        log.error("run %s stopped: %s", run_id, e)
    except Exception as e:  # noqa: BLE001 - 주간 배치는 죽지 않고 상태를 남긴다
        status = "error"
        ctx.warnings.append(f"{type(e).__name__}: {e}")
        log.exception("run %s failed", run_id)
    finally:
        db.finish_run(run_id, status, llm.tracker.total_usd)
    return RunOutcome(run_id, week, status, report_path, llm.tracker.total_usd, ctx.warnings)
