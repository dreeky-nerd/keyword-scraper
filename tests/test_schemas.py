from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from trendfinder.schemas import (
    Candidate,
    CriticVerdict,
    RawSignal,
    ReferenceLink,
    ReportCard,
    ScoredCandidate,
)


def make_signal(**over):
    base = dict(
        source="tiktok_cc",
        region="global",
        term="mouth taping",
        metric_name="hashtag_views_7d",
        metric_value=310.0,
        collected_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
        url="https://ads.tiktok.com/business/creativecenter/hashtag/mouthtaping",
        raw={"views": 1200000},
    )
    base.update(over)
    return RawSignal(**base)


def test_raw_signal_roundtrip():
    s = make_signal()
    assert s.source == "tiktok_cc"
    assert RawSignal.model_validate_json(s.model_dump_json()) == s


def test_raw_signal_rejects_unknown_source():
    with pytest.raises(ValidationError):
        make_signal(source="myspace")


def test_candidate_defaults_source_count_from_signals():
    c = Candidate(
        canonical_name="mouth taping",
        aliases=["입테이프"],
        kind="behavior",
        subcategory="sleep",
        is_wellness=True,
        signals=[make_signal(), make_signal(source="reddit")],
    )
    assert c.source_count == 2


def test_scored_candidate_requires_valid_lifecycle():
    c = Candidate(
        canonical_name="x", aliases=[], kind="product", subcategory="other",
        is_wellness=True, signals=[],
    )
    with pytest.raises(ValidationError):
        ScoredCandidate(
            **c.model_dump(), hot_score=1.0, z_scores={}, lifecycle="HOT",
            gap_label="UNKNOWN", analyst_notes="", warnings=[],
        )


def test_report_card_and_reference_link():
    sc = ScoredCandidate(
        canonical_name="mouth taping", aliases=[], kind="behavior", subcategory="sleep",
        is_wellness=True, signals=[make_signal()], hot_score=4.2, z_scores={"tiktok_cc": 3.1},
        lifecycle="NEW", gap_label="GLOBAL_ONLY", analyst_notes="", warnings=[],
    )
    card = ReportCard(
        candidate=sc, rank=3, popup_form="클래스·이벤트", brands=["Hostage Tape"],
        evidence_urls=["https://reddit.com/r/sleep/1"],
        reference_urls=[ReferenceLink(kind="explainer", url="https://x/y", title="What is mouth taping", region="global")],
        one_liner="수면 중 입 테이프",
    )
    assert card.reference_urls[0].kind == "explainer"


def test_critic_verdict_literal():
    assert CriticVerdict(verdict="PASS", issues=[]).verdict == "PASS"
    with pytest.raises(ValidationError):
        CriticVerdict(verdict="MAYBE", issues=[])
