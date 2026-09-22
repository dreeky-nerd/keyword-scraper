"""Fixture-backed stand-ins for the four teams. Replaced one by one in plans 2-5."""

import json
from pathlib import Path

from ..schemas import Candidate, CriticVerdict, RawSignal, ReportCard, ScoredCandidate
from .base import StageContext

PASS = CriticVerdict(verdict="PASS")


class StubCollect:
    name = "collect"

    def __init__(self, fixture: Path):
        self.fixture = Path(fixture)

    def produce(self, ctx: StageContext, inputs: None, issues: list[str]) -> list[RawSignal]:
        data = json.loads(self.fixture.read_text(encoding="utf-8"))
        return [RawSignal.model_validate(d) for d in data]

    def critique(self, ctx: StageContext, output: list[RawSignal]) -> CriticVerdict:
        return PASS


class StubCurate:
    name = "curate"

    def __init__(self, fixture: Path):
        self.fixture = Path(fixture)

    def produce(self, ctx: StageContext, inputs: list[RawSignal], issues: list[str]) -> list[Candidate]:
        data = json.loads(self.fixture.read_text(encoding="utf-8"))
        return [Candidate.model_validate(d) for d in data]

    def critique(self, ctx: StageContext, output: list[Candidate]) -> CriticVerdict:
        return PASS


class StubAnalyze:
    name = "analyze"

    def produce(self, ctx: StageContext, inputs: list[Candidate], issues: list[str]) -> list[ScoredCandidate]:
        out = []
        for c in inputs:
            score = sum(s.metric_value for s in c.signals) / 100
            out.append(ScoredCandidate(
                **c.model_dump(), hot_score=round(score, 2), z_scores={},
                lifecycle="NEW", gap_label="UNKNOWN",
            ))
        return out

    def critique(self, ctx: StageContext, output: list[ScoredCandidate]) -> CriticVerdict:
        return PASS


class StubReport:
    name = "report"

    def produce(self, ctx: StageContext, inputs: list[ScoredCandidate], issues: list[str]) -> list[ReportCard]:
        ranked = sorted(inputs, key=lambda s: s.hot_score, reverse=True)[:10]
        return [
            ReportCard(candidate=s, rank=i + 1, popup_form="미정", one_liner=s.canonical_name)
            for i, s in enumerate(ranked)
        ]

    def critique(self, ctx: StageContext, output: list[ReportCard]) -> CriticVerdict:
        return PASS


def render_markdown(week: str, cards: list[ReportCard]) -> str:
    lines = [f"# 주간 웰니스 트렌드 {week}", ""]
    for card in cards:
        c = card.candidate
        lines.append(f"## {card.rank}. {c.canonical_name}  [{c.kind} · {c.subcategory}]  {c.gap_label} · {c.lifecycle}")
        signal_bits = " | ".join(f"{s.source} {s.metric_name}={s.metric_value:g}" for s in c.signals)
        lines.append(f"hot_score {c.hot_score:.2f} | {signal_bits}")
        lines.append(f"팝업 형태: {card.popup_form}")
        if card.brands:
            lines.append("브랜드: " + ", ".join(card.brands))
        if card.evidence_urls:
            lines.append("근거: " + " ".join(f"[{i+1}]({u})" for i, u in enumerate(card.evidence_urls)))
        if card.reference_urls:
            lines.append("참조: " + " ".join(f"[{r.title}]({r.url})" for r in card.reference_urls))
        for w in c.warnings:
            lines.append(f"경고: {w}")
        lines.append("")
    return "\n".join(lines)
