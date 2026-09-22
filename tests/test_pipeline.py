from pathlib import Path

from trendfinder.config import Settings
from trendfinder.db import Database
from trendfinder.llm import CostCapExceeded, LLMClient
from trendfinder.pipeline import Stages, run_week
from trendfinder.schemas import CriticVerdict
from trendfinder.teams.stubs import StubAnalyze, StubCollect, StubCurate, StubReport

FIX = Path(__file__).parent / "fixtures"


def make(tmp_path, fake_client, **over):
    settings = Settings(db_path=tmp_path / "t.sqlite", reports_dir=tmp_path / "reports", **over)
    db = Database(settings.db_path)
    db.init_schema()
    stages = Stages(
        collect=StubCollect(FIX / "raw_signals.json"),
        curate=StubCurate(FIX / "candidates.json"),
        analyze=StubAnalyze(),
        report=StubReport(),
    )
    return settings, db, stages, LLMClient(fake_client, settings)


def test_run_week_end_to_end_writes_report(tmp_path, fake_client):
    settings, db, stages, llm = make(tmp_path, fake_client)
    out = run_week("2026-W39", stages, db, llm, settings)
    assert out.status == "ok"
    assert out.report_path == tmp_path / "reports" / "2026-W39.md"
    text = out.report_path.read_text(encoding="utf-8")
    assert "## 1. mouth taping" in text
    assert db.get_history("mouth taping", 1) == [("2026-W39", 5.72, "NEW")]
    assert db.conn.execute("select status from runs where run_id=?", (out.run_id,)).fetchone()[0] == "ok"
    assert db.conn.execute("select count(*) from raw_signals").fetchone()[0] == 5
    assert db.conn.execute("select count(*) from candidates").fetchone()[0] == 2
    assert db.conn.execute("select markdown from reports where run_id=?", (out.run_id,)).fetchone()[0] == text
    assert [v for _, _, v, _ in db.get_critic_logs(out.run_id)] == ["PASS"] * 4


class RejectingCollect(StubCollect):
    def critique(self, ctx, output):
        return CriticVerdict(verdict="REJECT", issues=["3 sources failed"])


def test_reject_marks_run_and_writes_no_report(tmp_path, fake_client):
    settings, db, stages, llm = make(tmp_path, fake_client)
    stages.collect = RejectingCollect(FIX / "raw_signals.json")
    out = run_week("2026-W39", stages, db, llm, settings)
    assert out.status == "rejected"
    assert out.report_path is None
    assert "3 sources failed" in out.warnings[0]
    assert not (tmp_path / "reports").exists() or not list((tmp_path / "reports").glob("*.md"))


class RevisingCurate(StubCurate):
    def __init__(self, fixture):
        super().__init__(fixture)
        self.n = 0

    def critique(self, ctx, output):
        self.n += 1
        return CriticVerdict(verdict="REVISE", issues=[f"issue {self.n}"])


def test_revise_limit_adds_warning_and_continues(tmp_path, fake_client):
    settings, db, stages, llm = make(tmp_path, fake_client)
    stages.curate = RevisingCurate(FIX / "candidates.json")
    out = run_week("2026-W39", stages, db, llm, settings)
    assert out.status == "ok"
    assert "issue 2" in out.warnings
    logs = [(t, a, v) for t, a, v, _ in db.get_critic_logs(out.run_id) if t == "curate"]
    assert logs == [("curate", 1, "REVISE"), ("curate", 2, "REVISE")]


class ExpensiveAnalyze(StubAnalyze):
    def produce(self, ctx, inputs, issues):
        raise CostCapExceeded("too much")


def test_cost_cap_sets_status(tmp_path, fake_client):
    settings, db, stages, llm = make(tmp_path, fake_client)
    stages.analyze = ExpensiveAnalyze()
    out = run_week("2026-W39", stages, db, llm, settings)
    assert out.status == "cost_cap"
    assert out.report_path is None
