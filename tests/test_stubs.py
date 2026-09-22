from pathlib import Path

from trendfinder.config import Settings
from trendfinder.db import Database
from trendfinder.llm import LLMClient
from trendfinder.schemas import CriticVerdict
from trendfinder.teams.base import StageContext
from trendfinder.teams.stubs import StubAnalyze, StubCollect, StubCurate, StubReport, render_markdown

FIX = Path(__file__).parent / "fixtures"


def ctx(tmp_path, fake_client):
    db = Database(tmp_path / "t.sqlite")
    db.init_schema()
    return StageContext(run_id=1, week="2026-W39", db=db, llm=LLMClient(fake_client, Settings()), settings=Settings())


def test_stub_collect_reads_fixture(tmp_path, fake_client):
    c = ctx(tmp_path, fake_client)
    signals = StubCollect(FIX / "raw_signals.json").produce(c, None, [])
    assert len(signals) == 5
    assert signals[0].source == "tiktok_cc"
    assert StubCollect(FIX / "raw_signals.json").critique(c, signals) == CriticVerdict(verdict="PASS")


def test_stub_curate_reads_fixture(tmp_path, fake_client):
    c = ctx(tmp_path, fake_client)
    cands = StubCurate(FIX / "candidates.json").produce(c, [], [])
    assert [x.canonical_name for x in cands] == ["mouth taping", "cold plunge"]
    assert cands[0].source_count == 3


def test_stub_analyze_scores_by_signal_sum(tmp_path, fake_client):
    c = ctx(tmp_path, fake_client)
    cands = StubCurate(FIX / "candidates.json").produce(c, [], [])
    scored = StubAnalyze().produce(c, cands, [])
    by = {s.canonical_name: s for s in scored}
    assert by["mouth taping"].hot_score == (310 + 12 + 250) / 100
    assert by["cold plunge"].hot_score == (40 + 55) / 100
    assert by["mouth taping"].lifecycle == "NEW"


def test_stub_report_ranks_top10(tmp_path, fake_client):
    c = ctx(tmp_path, fake_client)
    cands = StubCurate(FIX / "candidates.json").produce(c, [], [])
    scored = StubAnalyze().produce(c, cands, [])
    cards = StubReport().produce(c, scored, [])
    assert [k.candidate.canonical_name for k in cards] == ["mouth taping", "cold plunge"]
    assert [k.rank for k in cards] == [1, 2]


def test_render_markdown_has_card_per_candidate(tmp_path, fake_client):
    c = ctx(tmp_path, fake_client)
    cands = StubCurate(FIX / "candidates.json").produce(c, [], [])
    cards = StubReport().produce(c, StubAnalyze().produce(c, cands, []), [])
    md = render_markdown("2026-W39", cards)
    assert md.startswith("# 주간 웰니스 트렌드 2026-W39")
    assert "## 1. mouth taping" in md
    assert "## 2. cold plunge" in md
    assert "hot_score 5.72" in md
