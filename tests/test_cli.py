import shutil
from pathlib import Path

import pytest

from trendfinder.cli import main

FIX = Path(__file__).parent / "fixtures"


def test_run_stub_mode_writes_report_and_exits_zero(tmp_path, capsys):
    fixtures = tmp_path / "fixtures"
    shutil.copytree(FIX, fixtures)
    code = main([
        "run", "--week", "2026-W39", "--mode", "stub",
        "--db", str(tmp_path / "t.sqlite"),
        "--reports-dir", str(tmp_path / "reports"),
        "--fixtures-dir", str(fixtures),
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert out.startswith("2026-W39 ok cost=$0.00 report=")
    assert (tmp_path / "reports" / "2026-W39.md").exists()


def test_run_defaults_to_current_week(tmp_path, monkeypatch):
    fixtures = tmp_path / "fixtures"
    shutil.copytree(FIX, fixtures)
    monkeypatch.setenv("TF_DB_PATH", str(tmp_path / "t.sqlite"))
    monkeypatch.setenv("TF_REPORTS_DIR", str(tmp_path / "reports"))
    code = main(["run", "--mode", "stub", "--fixtures-dir", str(fixtures)])
    assert code == 0
    assert len(list((tmp_path / "reports").glob("*-W*.md"))) == 1


def test_live_mode_not_implemented_yet(tmp_path):
    with pytest.raises(NotImplementedError):
        main(["run", "--mode", "live", "--db", str(tmp_path / "t.sqlite")])
