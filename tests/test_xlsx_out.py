from bidtriage.draft_schema import PriceLine
from bidtriage.xlsx_out import HEADERS, build_price_bid
from tests.draft_fixtures import sample_draft


def _rows(ws):
    return [[c.value for c in row] for row in ws.iter_rows()]


def _line_row(ws, description):
    return next(r for r in ws.iter_rows() if r[1].value == description)


def test_price_lines_and_quantities():
    ws = build_price_bid(sample_draft()).active
    rows = _rows(ws)
    assert HEADERS in rows
    assert ["Design Phase (DP)"] == [v for v in rows[rows.index(HEADERS) + 1] if v]
    assert _line_row(ws, "Indigenised PSM (ESS Units)")[2].value == 4
    assert _line_row(ws, "Indigenised PSM (1st Year)")[2].value == 10


def test_price_cells_blank_and_highlighted():
    row = _line_row(build_price_bid(sample_draft()).active, "Indigenised PSM (ESS Units)")
    unit, gst = row[3], row[5]
    assert unit.value is None and gst.value is None
    assert unit.fill.fgColor.rgb.endswith("FFFF00") and gst.fill.fgColor.rgb.endswith("FFFF00")


def test_totals_are_formulas():
    ws = build_price_bid(sample_draft()).active
    row = _line_row(ws, "Indigenised PSM (ESS Units)")
    r = row[0].row
    assert row[4].value == f"=IF(D{r}=\"\",\"\",C{r}*D{r})"
    assert row[6].value == f"=IF(OR(E{r}=\"\",F{r}=\"\"),\"\",E{r}*(1+F{r}/100))"
    values = [v for line in _rows(ws) for v in line if isinstance(v, str)]
    assert any(v.startswith("=SUM(") for v in values)
    assert "Grand Total" in values


def test_non_numeric_qty_leaves_formula_cells_blank():
    d = sample_draft()
    d.price_lines = [PriceLine(phase="PP", sno="1", description="Spares", qty="as required")]
    row = _line_row(build_price_bid(d).active, "Spares")
    assert row[2].value == "as required"
    assert row[4].value is None and row[6].value is None
