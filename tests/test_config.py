from datetime import date
from pathlib import Path

from trendfinder.config import PRICES, Settings, week_id


def test_week_id_iso_format():
    assert week_id(date(2026, 9, 22)) == "2026-W39"
    assert week_id(date(2026, 1, 1)) == "2026-W01"


def test_settings_defaults():
    s = Settings()
    assert s.model_worker == "claude-sonnet-5"
    assert s.model_critic == "claude-opus-5"
    assert s.model_lead == "claude-fable-5-1"
    assert s.cost_cap_usd == 30.0
    assert s.max_revise == 1


def test_settings_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("TF_DB_PATH", str(tmp_path / "t.sqlite"))
    monkeypatch.setenv("TF_REPORTS_DIR", str(tmp_path / "r"))
    monkeypatch.setenv("TF_COST_CAP_USD", "12.5")
    s = Settings.from_env()
    assert s.db_path == tmp_path / "t.sqlite"
    assert s.reports_dir == tmp_path / "r"
    assert s.cost_cap_usd == 12.5


def test_prices_cover_all_models():
    assert PRICES["claude-sonnet-5"] == (2.0, 10.0)
    assert PRICES["claude-opus-5"] == (5.0, 25.0)
    assert PRICES["claude-fable-5-1"] == (10.0, 50.0)
