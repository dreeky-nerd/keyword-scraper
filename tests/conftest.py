from collections import deque
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class FakeUsage:
    input_tokens: int = 1000
    output_tokens: int = 200


@dataclass
class FakeResponse:
    parsed_output: Any = None
    stop_reason: str = "end_turn"
    usage: FakeUsage = field(default_factory=FakeUsage)
    model: str = "claude-sonnet-5"


class FakeMessages:
    def __init__(self):
        self.queue: deque[FakeResponse] = deque()
        self.calls: list[dict] = []

    def parse(self, **kwargs) -> FakeResponse:
        self.calls.append(kwargs)
        if not self.queue:
            raise AssertionError("FakeAnthropic: no queued response")
        return self.queue.popleft()


class FakeAnthropic:
    def __init__(self):
        self.messages = FakeMessages()

    def push(self, *responses: FakeResponse) -> None:
        self.messages.queue.extend(responses)


@pytest.fixture
def fake_client() -> FakeAnthropic:
    return FakeAnthropic()
