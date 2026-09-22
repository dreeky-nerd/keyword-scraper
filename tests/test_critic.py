import pytest

from trendfinder.critic import PipelineRejected, run_with_critic
from trendfinder.schemas import CriticVerdict


def test_pass_first_time():
    res = run_with_critic("t", lambda issues: "out", lambda o: CriticVerdict(verdict="PASS"))
    assert res.output == "out"
    assert res.attempts == 1
    assert res.warnings == []


def test_revise_once_then_pass():
    seen = []
    verdicts = iter([CriticVerdict(verdict="REVISE", issues=["stale"]), CriticVerdict(verdict="PASS")])

    def produce(issues):
        seen.append(list(issues))
        return f"v{len(seen)}"

    res = run_with_critic("t", produce, lambda o: next(verdicts))
    assert res.output == "v2"
    assert seen == [[], ["stale"]]
    assert res.attempts == 2
    assert res.warnings == []


def test_revise_limit_reached_returns_with_warnings():
    verdicts = iter([
        CriticVerdict(verdict="REVISE", issues=["a"]),
        CriticVerdict(verdict="REVISE", issues=["b"]),
    ])
    res = run_with_critic("t", lambda issues: "x", lambda o: next(verdicts), max_revise=1)
    assert res.output == "x"
    assert res.attempts == 2
    assert res.warnings == ["b"]
    assert [v.verdict for v in res.verdicts] == ["REVISE", "REVISE"]


def test_reject_raises():
    with pytest.raises(PipelineRejected) as ei:
        run_with_critic("collect", lambda i: "x", lambda o: CriticVerdict(verdict="REJECT", issues=["no data"]))
    assert ei.value.team == "collect"
    assert ei.value.issues == ["no data"]
