from datetime import datetime, timezone

from trendfinder.db import Database
from trendfinder.schemas import Candidate, CriticVerdict, RawSignal, ScoredCandidate


def sig(source="reddit"):
    return RawSignal(
        source=source, region="global", term="cold plunge", metric_name="posts_7d",
        metric_value=12, collected_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
    )


def scored(name, score, lifecycle):
    return ScoredCandidate(
        canonical_name=name, aliases=[], kind="behavior", subcategory="recovery",
        is_wellness=True, signals=[sig()], hot_score=score, z_scores={}, lifecycle=lifecycle,
        gap_label="UNKNOWN",
    )


def test_run_lifecycle(tmp_path):
    with Database(tmp_path / "t.sqlite") as db:
        db.init_schema()
        run_id = db.start_run("2026-W39")
        db.finish_run(run_id, "ok", 1.25)
        row = db.conn.execute("select week, status, cost_usd from runs where run_id=?", (run_id,)).fetchone()
        assert row == ("2026-W39", "ok", 1.25)


def test_signals_and_candidates_roundtrip(tmp_path):
    with Database(tmp_path / "t.sqlite") as db:
        db.init_schema()
        run_id = db.start_run("2026-W39")
        db.save_raw_signals(run_id, [sig(), sig("tiktok_cc")])
        db.save_candidates(run_id, [Candidate(
            canonical_name="cold plunge", aliases=["냉수욕"], kind="behavior",
            subcategory="recovery", is_wellness=True, signals=[sig()],
        )])
        n = db.conn.execute("select count(*) from raw_signals where run_id=?", (run_id,)).fetchone()[0]
        assert n == 2
        name = db.conn.execute("select canonical_name from candidates where run_id=?", (run_id,)).fetchone()[0]
        assert name == "cold plunge"


def test_history_returns_latest_first(tmp_path):
    with Database(tmp_path / "t.sqlite") as db:
        db.init_schema()
        db.save_history("2026-W37", [scored("cold plunge", 1.0, "NEW")])
        db.save_history("2026-W38", [scored("cold plunge", 2.5, "RISING")])
        db.save_history("2026-W39", [scored("cold plunge", 3.0, "RISING")])
        hist = db.get_history("cold plunge", weeks=2)
        assert hist == [("2026-W39", 3.0, "RISING"), ("2026-W38", 2.5, "RISING")]


def test_history_upsert_same_week(tmp_path):
    with Database(tmp_path / "t.sqlite") as db:
        db.init_schema()
        db.save_history("2026-W39", [scored("x", 1.0, "NEW")])
        db.save_history("2026-W39", [scored("x", 9.0, "PEAK")])
        assert db.get_history("x", weeks=5) == [("2026-W39", 9.0, "PEAK")]


def test_report_and_critic_logs(tmp_path):
    with Database(tmp_path / "t.sqlite") as db:
        db.init_schema()
        run_id = db.start_run("2026-W39")
        db.save_report(run_id, "# report")
        db.log_critic(run_id, "collect", 1, CriticVerdict(verdict="REVISE", issues=["stale"]))
        db.log_critic(run_id, "collect", 2, CriticVerdict(verdict="PASS", issues=[]))
        assert db.get_critic_logs(run_id) == [
            ("collect", 1, "REVISE", ["stale"]),
            ("collect", 2, "PASS", []),
        ]
