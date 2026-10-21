from datetime import date

import pytest

import triage
from bidtriage.analyzer import AnalysisError
from tests.fixtures import sample_assessment


@pytest.fixture
def bid_dir(tmp_path):
    d = tmp_path / "bid"
    d.mkdir()
    (d / "email.txt").write_text("Subject: AHRU test\n\nPlease check.", encoding="utf-8")
    (d / "a.pdf").write_bytes(b"%PDF-1.4")
    return d


def test_output_dir_slug_is_filesystem_safe(tmp_path):
    d = triage.output_dir(tmp_path, sample_assessment(), "subj", date(2026, 10, 21))
    assert d.name == "2026-10-21_hal-hyd-imm-indg-m1-psm-ahru-2026-01"


def test_main_writes_three_files(tmp_path, monkeypatch, bid_dir):
    monkeypatch.setattr(triage, "analyze", lambda *a, **k: sample_assessment())
    out = tmp_path / "out"
    assert triage.main([str(bid_dir), "--out", str(out)]) == 0
    files = sorted(p.name for p in next(out.iterdir()).iterdir())
    assert files == ["assessment.json", "card.html", "card.md"]


def test_main_reports_analysis_error_and_writes_nothing(tmp_path, monkeypatch, capsys, bid_dir):
    def fail(*a, **k):
        raise AnalysisError("Claude stopped with refusal; no card written")

    monkeypatch.setattr(triage, "analyze", fail)
    out = tmp_path / "out"
    assert triage.main([str(bid_dir), "--out", str(out)]) == 1
    assert "error: Claude stopped with refusal" in capsys.readouterr().err
    assert not out.exists()
