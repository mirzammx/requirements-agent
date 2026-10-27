import json
from datetime import date

import shortlist as shortlist_cli
from bidtriage.bidassist import Tender
from bidtriage.shortlist_out import build_tracker, render_digest
from bidtriage.shortlister import Shortlisted
from tests.test_bidassist import HEADER, make_xlsx, row

TODAY = date(2026, 10, 10)


def item(tid, category, days, summary="Item", route="SBU-2", reason="why"):
    return Shortlisted(Tender(tender_id=tid, authority="BEL", summary=summary, closing_date="x"),
                       category, route, "high", reason, days)


ITEMS = [
    item("LATE", "sbu2_power", 10, summary="AC-DC PSU"),
    item("SOON", "sbu2_power", 2, summary="Variable SMPS"),
    item("CIV", "not_relevant", 5, summary="Power supply to barriers", route="none"),
    item("SRV", "other_product_line", 5, summary="GPU server", route="Computing/Servers"),
    item("UNK", "manual_check", None, route=""),
]


def test_digest_sections_and_sorting():
    html = render_digest(ITEMS, TODAY)
    order = ["SBU-2 power supply candidates", "Needs manual check", "Other product lines", "Not relevant"]
    assert [html.index(h) for h in order] == sorted(html.index(h) for h in order)
    assert html.index("Variable SMPS") < html.index("AC-DC PSU")
    assert "Computing/Servers" in html


def test_digest_escapes():
    html = render_digest([item("X", "sbu2_power", 1, summary="<b>bad</b>")], TODAY)
    assert "<b>bad</b>" not in html and "&lt;b&gt;bad&lt;/b&gt;" in html


def test_tracker_has_decision_dropdown():
    ws = build_tracker(ITEMS).active
    headers = [c.value for c in ws[1]]
    assert "Decision" in headers and "Reason" in headers
    assert ws.cell(2, headers.index("Tender Id") + 1).value == "SOON"
    dv = ws.data_validations.dataValidation[0]
    assert dv.formula1 == '"Go,No-go,Ask"'


def test_cli_writes_outputs(tmp_path, monkeypatch):
    f = make_xlsx(tmp_path / "Power supply-Tender List.xlsx", {"Tender List": [HEADER, row("G1", "SMPS")]})
    monkeypatch.setattr(shortlist_cli, "classify", lambda tenders, **k: [item(t.tender_id, "sbu2_power", 3)
                                                                         for t in tenders])
    assert shortlist_cli.main([str(f), "--out", str(tmp_path / "out")]) == 0
    folder = next((tmp_path / "out").iterdir())
    assert folder.name.startswith("shortlist_")
    assert sorted(p.name for p in folder.iterdir()) == ["digest.html", "shortlist.json", "shortlist.xlsx"]
    assert json.loads((folder / "shortlist.json").read_text(encoding="utf-8"))[0]["tender_id"] == "G1"


def test_cli_bad_file_errors(tmp_path, capsys):
    f = make_xlsx(tmp_path / "x.xlsx", {"S": [["nothing"]]})
    assert shortlist_cli.main([str(f), "--out", str(tmp_path / "out")]) == 1
    assert "error:" in capsys.readouterr().err


def test_second_run_same_day_does_not_overwrite(tmp_path, monkeypatch):
    f = make_xlsx(tmp_path / "Power supply-Tender List.xlsx", {"Tender List": [HEADER, row("G1", "SMPS")]})
    monkeypatch.setattr(shortlist_cli, "classify", lambda tenders, **k: [item(t.tender_id, "sbu2_power", 3)
                                                                         for t in tenders])
    assert shortlist_cli.main([str(f), "--out", str(tmp_path / "out")]) == 0
    assert shortlist_cli.main([str(f), "--out", str(tmp_path / "out")]) == 0
    assert len(list((tmp_path / "out").iterdir())) == 2