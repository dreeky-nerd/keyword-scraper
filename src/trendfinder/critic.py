"""Critic protocol (spec §6): PASS / REVISE (max N) / REJECT. Pure control flow, no LLM."""

from dataclasses import dataclass, field
from typing import Callable, Generic, TypeVar

from .schemas import CriticVerdict

T = TypeVar("T")


class PipelineRejected(Exception):
    def __init__(self, team: str, issues: list[str]):
        super().__init__(f"{team} rejected: {issues}")
        self.team = team
        self.issues = issues


@dataclass
class StageResult(Generic[T]):
    output: T
    warnings: list[str] = field(default_factory=list)
    attempts: int = 0
    verdicts: list[CriticVerdict] = field(default_factory=list)


def run_with_critic(
    team: str,
    produce: Callable[[list[str]], T],
    critique: Callable[[T], CriticVerdict],
    max_revise: int = 1,
) -> StageResult[T]:
    issues: list[str] = []
    verdicts: list[CriticVerdict] = []
    output = produce(issues)
    for attempt in range(1, max_revise + 2):
        verdict = critique(output)
        verdicts.append(verdict)
        if verdict.verdict == "PASS":
            return StageResult(output=output, attempts=attempt, verdicts=verdicts)
        if verdict.verdict == "REJECT":
            raise PipelineRejected(team, verdict.issues)
        issues = verdict.issues
        if attempt <= max_revise:
            output = produce(issues)
    return StageResult(output=output, warnings=list(issues), attempts=max_revise + 1, verdicts=verdicts)
