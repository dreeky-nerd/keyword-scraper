import pytest
from pydantic import BaseModel

from trendfinder.config import Settings
from trendfinder.llm import CostCapExceeded, CostTracker, LLMClient, LLMParseError, LLMRefused
from tests.conftest import FakeResponse, FakeUsage


class Out(BaseModel):
    answer: str


def test_cost_tracker_uses_price_table():
    t = CostTracker()
    t.add("claude-sonnet-5", input_tokens=1_000_000, output_tokens=100_000)
    assert t.total_usd == pytest.approx(2.0 + 1.0)
    t.add("claude-fable-5-1", input_tokens=100_000, output_tokens=10_000)
    assert t.total_usd == pytest.approx(3.0 + 1.0 + 0.5)
    assert t.calls == 2


def test_structured_returns_parsed_and_tracks_cost(fake_client):
    fake_client.push(FakeResponse(parsed_output=Out(answer="hi"), usage=FakeUsage(1000, 500)))
    llm = LLMClient(fake_client, Settings())
    out = llm.structured("claude-sonnet-5", "sys", "user", Out, effort="low")
    assert out == Out(answer="hi")
    assert llm.tracker.total_usd == pytest.approx(0.002 + 0.005)
    call = fake_client.messages.calls[0]
    assert call["model"] == "claude-sonnet-5"
    assert call["output_format"] is Out
    assert call["output_config"] == {"effort": "low"}
    assert call["messages"] == [{"role": "user", "content": "user"}]


def test_refusal_falls_back_to_opus_once(fake_client):
    fake_client.push(
        FakeResponse(stop_reason="refusal", model="claude-fable-5-1"),
        FakeResponse(parsed_output=Out(answer="ok"), model="claude-opus-5"),
    )
    llm = LLMClient(fake_client, Settings())
    assert llm.structured("claude-fable-5-1", "s", "u", Out).answer == "ok"
    assert [c["model"] for c in fake_client.messages.calls] == ["claude-fable-5-1", "claude-opus-5"]


def test_double_refusal_raises(fake_client):
    fake_client.push(FakeResponse(stop_reason="refusal"), FakeResponse(stop_reason="refusal"))
    llm = LLMClient(fake_client, Settings())
    with pytest.raises(LLMRefused):
        llm.structured("claude-fable-5-1", "s", "u", Out)


def test_parse_failure_retries_once_then_raises(fake_client):
    fake_client.push(FakeResponse(parsed_output=None), FakeResponse(parsed_output=None))
    llm = LLMClient(fake_client, Settings())
    with pytest.raises(LLMParseError):
        llm.structured("claude-sonnet-5", "s", "u", Out)
    assert len(fake_client.messages.calls) == 2


def test_cost_cap_exceeded(fake_client):
    fake_client.push(FakeResponse(parsed_output=Out(answer="x"), usage=FakeUsage(10_000_000, 0)))
    llm = LLMClient(fake_client, Settings(cost_cap_usd=1.0))
    with pytest.raises(CostCapExceeded):
        llm.structured("claude-opus-5", "s", "u", Out)
