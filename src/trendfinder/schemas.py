"""Data contracts between teams (spec §7). Shapes only, no logic."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Source = Literal["tiktok_cc", "google_trends", "reddit", "instagram", "naver_datalab"]
Region = Literal["global", "kr"]
Kind = Literal["product", "behavior"]
Lifecycle = Literal["NEW", "RISING", "PEAK", "DECLINING", "WATCHING"]
GapLabel = Literal["GLOBAL_ONLY", "KR_HOT", "KR_PAST_PEAK", "UNKNOWN"]
Verdict = Literal["PASS", "REVISE", "REJECT"]
LinkKind = Literal["brand_official", "product_page", "explainer", "how_to"]


class RawSignal(BaseModel):
    source: Source
    region: Region
    term: str
    metric_name: str
    metric_value: float
    collected_at: datetime
    url: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class Candidate(BaseModel):
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    kind: Kind
    subcategory: str
    is_wellness: bool
    signals: list[RawSignal] = Field(default_factory=list)
    source_count: int = 0

    @model_validator(mode="after")
    def _derive_source_count(self) -> "Candidate":
        if self.source_count == 0 and self.signals:
            self.source_count = len({s.source for s in self.signals})
        return self


class ScoredCandidate(Candidate):
    hot_score: float
    z_scores: dict[str, float] = Field(default_factory=dict)
    lifecycle: Lifecycle
    gap_label: GapLabel
    analyst_notes: str = ""
    warnings: list[str] = Field(default_factory=list)


class ReferenceLink(BaseModel):
    kind: LinkKind
    url: str
    title: str
    region: Region


class ReportCard(BaseModel):
    candidate: ScoredCandidate
    rank: int
    popup_form: str
    brands: list[str] = Field(default_factory=list)
    evidence_urls: list[str] = Field(default_factory=list)
    reference_urls: list[ReferenceLink] = Field(default_factory=list)
    one_liner: str


class CriticVerdict(BaseModel):
    verdict: Verdict
    issues: list[str] = Field(default_factory=list)
