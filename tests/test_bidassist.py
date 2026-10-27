from datetime import date

import openpyxl
import pytest

from bidtriage.bidassist import parse_date, read_tender_lists

HEADER = ["Tender Id", "Tender No", "Tender Authority", "Tender Amount", "Opening Date", "Closing Date", "EMD",
          "Document Cost", "Tender Fee", "Location", "Summary", "Description", "Matching Keyword",
          "Corrigendum (Y/N)"]


def row(tid, summary, closing="16-Oct-2026", corr="N", authority="Bharat Electronics Limited"):
    return [tid, tid, authority, "-", "25-Sep-2026", closing, "-", "-", "-", "Pune, Maharashtra", summary,
            summary, "power supply", corr]


def make_xlsx(path, sheets):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    wb.save(path)
    return path


def test_reads_both_sheets(tmp_path):
    f = make_xlsx(tmp_path / "Power supply-Tender List_26092026.xlsx", {
        "Tender List_26092026": [HEADER, row("GEM/2026/B/1", "Category: Variable SMPS")],
        "Tender Updated_26092026": [HEADER, row("GEM/2026/B/2", "Seal kit", corr="Y")],
    })
    tenders = read_tender_lists([f])
    assert [t.tender_id for t in tenders] == ["GEM/2026/B/1", "GEM/2026/B/2"]
    first, second = tenders
    assert first.authority == "Bharat Electronics Limited"
    assert first.closing_date == "16-Oct-2026"
    assert first.keyword == "power supply"
    assert not first.corrigendum and second.corrigendum
    assert "Power supply-Tender List_26092026.xlsx" in first.source


def test_header_found_below_title_rows(tmp_path):
    f = make_xlsx(tmp_path / "t.xlsx", {"S": [["BidAssist export"], [], HEADER, row("X1", "PSU")]})
    assert [t.tender_id for t in read_tender_lists([f])] == ["X1"]


def test_missing_header_raises(tmp_path):
    f = make_xlsx(tmp_path / "t.xlsx", {"S": [["a", "b"], ["c", "d"]]})
    with pytest.raises(ValueError, match="Tender Id"):
        read_tender_lists([f])


def test_dedupe_marks_corrigendum(tmp_path):
    a = make_xlsx(tmp_path / "a.xlsx", {"New": [HEADER, row("G1", "PSU")]})
    b = make_xlsx(tmp_path / "b.xlsx", {"Upd": [HEADER, row("G1", "PSU", corr="Y")]})
    tenders = read_tender_lists([a, b])
    assert len(tenders) == 1 and tenders[0].corrigendum


def test_parse_date():
    assert parse_date("16-Oct-2026") == date(2026, 10, 16)
    assert parse_date("-") is None and parse_date("") is None and parse_date("soon") is None
