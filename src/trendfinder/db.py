"""SQLite persistence (spec §9). SQL only; no business logic."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .schemas import Candidate, CriticVerdict, RawSignal, ScoredCandidate

SCHEMA = """
create table if not exists runs (
  run_id integer primary key autoincrement,
  week text not null,
  started_at text not null,
  finished_at text,
  status text not null default 'running',
  cost_usd real not null default 0
);
create table if not exists raw_signals (
  id integer primary key autoincrement,
  run_id integer not null references runs(run_id),
  source text not null, region text not null, term text not null,
  metric_name text not null, metric_value real not null,
  collected_at text not null, url text, raw text not null
);
create table if not exists candidates (
  id integer primary key autoincrement,
  run_id integer not null references runs(run_id),
  canonical_name text not null,
  payload text not null
);
create table if not exists candidate_history (
  canonical_name text not null,
  week text not null,
  hot_score real not null,
  lifecycle text not null,
  primary key (canonical_name, week)
);
create table if not exists reports (
  run_id integer primary key references runs(run_id),
  markdown text not null
);
create table if not exists critic_logs (
  id integer primary key autoincrement,
  run_id integer not null references runs(run_id),
  team text not null, attempt integer not null,
  verdict text not null, issues text not null
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc) -> None:
        self.conn.commit()
        self.conn.close()

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # runs
    def start_run(self, week: str) -> int:
        cur = self.conn.execute(
            "insert into runs(week, started_at) values (?, ?)", (week, _now())
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_run(self, run_id: int, status: str, cost_usd: float) -> None:
        self.conn.execute(
            "update runs set finished_at=?, status=?, cost_usd=? where run_id=?",
            (_now(), status, cost_usd, run_id),
        )
        self.conn.commit()

    # signals / candidates
    def save_raw_signals(self, run_id: int, signals: list[RawSignal]) -> None:
        self.conn.executemany(
            "insert into raw_signals(run_id, source, region, term, metric_name, metric_value, "
            "collected_at, url, raw) values (?,?,?,?,?,?,?,?,?)",
            [
                (run_id, s.source, s.region, s.term, s.metric_name, s.metric_value,
                 s.collected_at.isoformat(), s.url, json.dumps(s.raw, ensure_ascii=False))
                for s in signals
            ],
        )
        self.conn.commit()

    def save_candidates(self, run_id: int, cands: list[Candidate]) -> None:
        self.conn.executemany(
            "insert into candidates(run_id, canonical_name, payload) values (?,?,?)",
            [(run_id, c.canonical_name, c.model_dump_json()) for c in cands],
        )
        self.conn.commit()

    # history
    def save_history(self, week: str, scored: list[ScoredCandidate]) -> None:
        self.conn.executemany(
            "insert into candidate_history(canonical_name, week, hot_score, lifecycle) "
            "values (?,?,?,?) on conflict(canonical_name, week) do update set "
            "hot_score=excluded.hot_score, lifecycle=excluded.lifecycle",
            [(s.canonical_name, week, s.hot_score, s.lifecycle) for s in scored],
        )
        self.conn.commit()

    def get_history(self, canonical_name: str, weeks: int) -> list[tuple[str, float, str]]:
        rows = self.conn.execute(
            "select week, hot_score, lifecycle from candidate_history where canonical_name=? "
            "order by week desc limit ?",
            (canonical_name, weeks),
        ).fetchall()
        return [(w, float(h), lc) for w, h, lc in rows]

    # reports / critic
    def save_report(self, run_id: int, markdown: str) -> None:
        self.conn.execute(
            "insert into reports(run_id, markdown) values (?,?) "
            "on conflict(run_id) do update set markdown=excluded.markdown",
            (run_id, markdown),
        )
        self.conn.commit()

    def log_critic(self, run_id: int, team: str, attempt: int, verdict: CriticVerdict) -> None:
        self.conn.execute(
            "insert into critic_logs(run_id, team, attempt, verdict, issues) values (?,?,?,?,?)",
            (run_id, team, attempt, verdict.verdict, json.dumps(verdict.issues, ensure_ascii=False)),
        )
        self.conn.commit()

    def get_critic_logs(self, run_id: int) -> list[tuple[str, int, str, list[str]]]:
        rows = self.conn.execute(
            "select team, attempt, verdict, issues from critic_logs where run_id=? order by id",
            (run_id,),
        ).fetchall()
        return [(t, a, v, json.loads(i)) for t, a, v, i in rows]
