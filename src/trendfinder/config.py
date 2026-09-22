"""Runtime settings and constants."""

import os
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

# USD per 1M tokens: (input, output). Exact model IDs, no date suffixes.
PRICES: dict[str, tuple[float, float]] = {
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-fable-5-1": (10.0, 50.0),
}


class Settings(BaseModel):
    model_worker: str = "claude-sonnet-5"
    model_critic: str = "claude-opus-5"
    model_lead: str = "claude-fable-5-1"
    model_fallback: str = "claude-opus-5"
    cost_cap_usd: float = 30.0
    max_revise: int = 1
    db_path: Path = Field(default_factory=lambda: Path("data/trendfinder.sqlite"))
    reports_dir: Path = Field(default_factory=lambda: Path("reports"))
    fixtures_dir: Path = Field(default_factory=lambda: Path("fixtures"))

    @classmethod
    def from_env(cls) -> "Settings":
        kwargs: dict = {}
        if v := os.environ.get("TF_DB_PATH"):
            kwargs["db_path"] = Path(v)
        if v := os.environ.get("TF_REPORTS_DIR"):
            kwargs["reports_dir"] = Path(v)
        if v := os.environ.get("TF_FIXTURES_DIR"):
            kwargs["fixtures_dir"] = Path(v)
        if v := os.environ.get("TF_COST_CAP_USD"):
            kwargs["cost_cap_usd"] = float(v)
        return cls(**kwargs)


def week_id(d: date | None = None) -> str:
    d = d or date.today()
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"
