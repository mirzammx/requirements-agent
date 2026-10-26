"""Price bid workbook: the buyer's lines and quantities, prices left blank for BD.

Unit price and GST % cells are empty and yellow; every total is a formula, so BD
only types unit prices and GST rates.
"""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from bidtriage.draft_schema import ResponseDraft

HEADERS = ["S.No", "Description", "Qty (Nos)", "Unit Price excl. GST (Rs)", "Total excl. GST (Rs)", "GST %",
           "Total incl. GST (Rs)"]
YELLOW = PatternFill("solid", fgColor="FFFF00")
BOLD = Font(bold=True)


def _qty(value: str):
    text = value.strip()
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return text


def build_price_bid(draft: ResponseDraft) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Price Bid"
    ws.append([draft.price_schedule_title])
    ws["A1"].font = Font(bold=True, size=13)
    ws.append([f"RFQ No: {draft.rfq_number}", "", "", f"Due date: {draft.due_date}"])
    ws.append(["Enter unit prices and GST % in the yellow cells; totals calculate automatically. "
               "Check every line against the buyer's own price bid format before submission."])
    ws.append([])
    ws.append(HEADERS)
    for cell in ws[ws.max_row]:
        cell.font = BOLD
        cell.alignment = Alignment(wrap_text=True, vertical="top")

    subtotal_rows = []
    phases: dict[str, list] = {}
    for line in draft.price_lines:
        phases.setdefault(line.phase, []).append(line)
    for phase, lines in phases.items():
        ws.append([phase])
        ws.cell(ws.max_row, 1).font = BOLD
        first = ws.max_row + 1
        for line in lines:
            qty = _qty(line.qty)
            ws.append([line.sno, line.description, qty])
            r = ws.max_row
            ws.cell(r, 4).fill = YELLOW
            ws.cell(r, 6).fill = YELLOW
            if isinstance(qty, (int, float)):
                ws.cell(r, 5).value = f'=IF(D{r}="","",C{r}*D{r})'
                ws.cell(r, 7).value = f'=IF(OR(E{r}="",F{r}=""),"",E{r}*(1+F{r}/100))'
        last = ws.max_row
        ws.append(["", f"Sub Total ({phase})", "", "", f"=SUM(E{first}:E{last})", "", f"=SUM(G{first}:G{last})"])
        for cell in ws[ws.max_row]:
            cell.font = BOLD
        subtotal_rows.append(ws.max_row)

    ws.append([])
    e_refs = ",".join(f"E{r}" for r in subtotal_rows) or "0"
    g_refs = ",".join(f"G{r}" for r in subtotal_rows) or "0"
    ws.append(["", "Grand Total", "", "", f"=SUM({e_refs})", "", f"=SUM({g_refs})"])
    for cell in ws[ws.max_row]:
        cell.font = BOLD
    ws.append([])
    ws.append(["", "Grand Total (incl. GST) in words: Rupees ________________ Only"])
    ws.append(["", "Name & Signature of Executive with Seal"])

    for col, width in zip("ABCDEFG", (8, 55, 10, 18, 18, 8, 18)):
        ws.column_dimensions[col].width = width
    for row in ws.iter_rows(min_row=6):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
    return wb
