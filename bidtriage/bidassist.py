"""Read BidAssist alert exports (<alert>-Tender List_<date>.xlsx) into Tender rows."""

import warnings
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

COLUMNS = {
    "tender id": "tender_id", "tender no": "tender_no", "tender authority": "authority",
    "tender amount": "amount", "opening date": "opening_date", "closing date": "closing_date", "emd": "emd",
    "location": "location", "summary": "summary", "description": "description",
    "matching keyword": "keyword", "corrigendum (y/n)": "corrigendum",
}
HEADER_SCAN_ROWS = 15


@dataclass
class Tender:
    tender_id: str
    tender_no: str = ""
    authority: str = ""
    amount: str = ""
    opening_date: str = ""
    closing_date: str = ""
    emd: str = ""
    location: str = ""
    summary: str = ""
    description: str = ""
    keyword: str = ""
    corrigendum: bool = False
    source: str = ""


def parse_date(text: str) -> date | None:
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(text).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _cell(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d-%b-%Y")
    return "" if value is None else str(value).strip()


def _read_sheet(ws, source: str) -> list[Tender] | None:
    rows = list(ws.iter_rows(values_only=True))
    for i, raw in enumerate(rows[:HEADER_SCAN_ROWS]):
        names = [_cell(v).lower() for v in raw]
        if "tender id" not in names:
            continue
        index = {COLUMNS[n]: j for j, n in enumerate(names) if n in COLUMNS}
        tenders = []
        for data in rows[i + 1:]:
            values = {field: _cell(data[j]) if j < len(data) else "" for field, j in index.items()}
            if not values.get("tender_id"):
                continue
            values["corrigendum"] = values.get("corrigendum", "").upper().startswith("Y") \
                or ws.title.lower().startswith("tender updated")
            tenders.append(Tender(**values, source=source))
        return tenders
    return None


def read_tender_lists(paths: list[Path]) -> list[Tender]:
    import openpyxl

    by_id: dict[str, Tender] = {}
    for path in map(Path, paths):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # BidAssist files lack a default style
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            found_header = False
            for ws in wb.worksheets:
                tenders = _read_sheet(ws, f"{path.name} / {ws.title}")
                if tenders is None:
                    continue
                found_header = True
                for t in tenders:
                    if t.tender_id in by_id:
                        by_id[t.tender_id].corrigendum |= t.corrigendum
                    else:
                        by_id[t.tender_id] = t
        finally:
            wb.close()
        if not found_header:
            raise ValueError(f"{path.name}: no sheet with a 'Tender Id' header row; is this a BidAssist export?")
    return list(by_id.values())
