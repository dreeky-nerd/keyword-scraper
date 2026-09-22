"""Network boundary: structured Claude calls with cost tracking and refusal fallback."""

from typing import Any, TypeVar

from pydantic import BaseModel

from .config import PRICES, Settings

T = TypeVar("T", bound=BaseModel)


class CostCapExceeded(Exception):
    pass


class LLMRefused(Exception):
    pass


class LLMParseError(Exception):
    pass


class CostTracker:
    def __init__(self) -> None:
        self.total_usd = 0.0
        self.calls = 0

    def add(self, model: str, input_tokens: int, output_tokens: int) -> None:
        price_in, price_out = PRICES[model]
        self.total_usd += input_tokens / 1_000_000 * price_in + output_tokens / 1_000_000 * price_out
        self.calls += 1


class LLMClient:
    def __init__(self, client: Any, settings: Settings, tracker: CostTracker | None = None):
        self.client = client
        self.settings = settings
        self.tracker = tracker or CostTracker()

    def structured(
        self,
        model: str,
        system: str,
        user: str,
        schema: type[T],
        effort: str = "medium",
        max_tokens: int = 16000,
    ) -> T:
        response = self._call(model, system, user, schema, effort, max_tokens)
        if response.stop_reason == "refusal":
            response = self._call(self.settings.model_fallback, system, user, schema, effort, max_tokens)
            if response.stop_reason == "refusal":
                raise LLMRefused(f"{model} and {self.settings.model_fallback} both refused")
        if response.parsed_output is None:
            response = self._call(response.model, system, user, schema, effort, max_tokens)
            if response.parsed_output is None:
                raise LLMParseError(f"{model} returned no parseable output twice")
        return response.parsed_output

    def _call(self, model: str, system: str, user: str, schema: type[T], effort: str, max_tokens: int):
        response = self.client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            output_config={"effort": effort},
        )
        self.tracker.add(model, response.usage.input_tokens, response.usage.output_tokens)
        if self.tracker.total_usd > self.settings.cost_cap_usd:
            raise CostCapExceeded(
                f"run cost ${self.tracker.total_usd:.2f} exceeds cap ${self.settings.cost_cap_usd:.2f}"
            )
        return response
