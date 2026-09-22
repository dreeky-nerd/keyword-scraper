"""Stage protocol shared by all four teams."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..config import Settings
from ..db import Database
from ..llm import LLMClient
from ..schemas import CriticVerdict


@dataclass
class StageContext:
    run_id: int
    week: str
    db: Database
    llm: LLMClient
    settings: Settings
    warnings: list[str] = field(default_factory=list)


class Stage(Protocol):
    name: str

    def produce(self, ctx: StageContext, inputs: Any, issues: list[str]) -> Any: ...

    def critique(self, ctx: StageContext, output: Any) -> CriticVerdict: ...
