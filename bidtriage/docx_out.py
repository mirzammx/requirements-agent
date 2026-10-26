"""Word documents for the response pack, modelled on Rug-Rel's own compliance format.

Every [[...]] span is rendered bold on yellow highlight so nothing is missed. Each
document opens with a count of its placeholders.
"""

import re
from datetime import date

from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.shared import Pt

from bidtriage.draft_schema import ResponseDraft
from bidtriage.profile import fact

PLACEHOLDER_RE = re.compile(r"(\[\[.*?\]\])", re.S)
STATUS_TEXT = {"complied": "Complied", "noted": "Noted", "not_applicable": "Not applicable"}
PACK_FILES = ["Technical_Compliance.docx", "Compliance_Statement.docx", "Price_Bid.xlsx",
              "Declarations.docx", "PreBid_Queries.docx"]


def add_rich(paragraph, text: str):
    """Append text, highlighting every [[...]] placeholder."""
    for piece in PLACEHOLDER_RE.split(text):
        if not piece:
            continue
        run = paragraph.add_run(piece)
        if PLACEHOLDER_RE.fullmatch(piece):
            run.bold = True
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW
    return paragraph


def count_placeholders(text: str) -> int:
    return len(PLACEHOLDER_RE.findall(text))


def all_text(doc) -> str:
    parts = [p.text for p in doc.paragraphs]
    parts += [cell.text for t in doc.tables for row in t.rows for cell in row.cells]
    return "\n".join(parts)


def _new_doc(profile: dict[str, str]):
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    section = doc.sections[0]
    header = section.header.paragraphs[0]
    header.text = fact(profile, "company_name")
    header.runs[0].bold = True
    footer = section.footer.paragraphs[0]
    footer.text = (f"{fact(profile, 'address')}  |  Ph: {fact(profile, 'phone')}  |  "
                   f"{fact(profile, 'email')}  |  {fact(profile, 'website')}")
    footer.runs[0].font.size = Pt(8)
    return doc


def _finish(doc):
    """Insert the placeholder count as the first paragraph."""
    n = count_placeholders(all_text(doc))
    first = doc.paragraphs[0]
    note = first.insert_paragraph_before(
        f"{n} highlighted placeholder{'s' if n != 1 else ''} to complete before submission. "
        "Remove this line when done.")
    note.runs[0].italic = True
    return doc


def _table(doc, headers: list[str], rows: list[list[str]]):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for cell, h in zip(table.rows[0].cells, headers):
        cell.text = h
        cell.paragraphs[0].runs[0].bold = True
    for row in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, row):
            add_rich(cell.paragraphs[0], value)
    return table


def _signature(doc, profile: dict[str, str], today: date):
    doc.add_paragraph()
    for line in (f"Date: {today:%d.%m.%Y}", "Place: Bengaluru",
                 f"Authorised Signatory: {fact(profile, 'authorised_signatory')}",
                 f"Designation: {fact(profile, 'signatory_designation')}",
                 f"For {fact(profile, 'company_name')} (Seal)"):
        add_rich(doc.add_paragraph(), line)


def _compliance_text(status: str, response: str) -> str:
    if status in ("review", "deviation"):
        return response
    label = STATUS_TEXT.get(status, status)
    return response if response.lower().startswith(label.lower()) else f"{label}. {response}".strip(". ")


def build_technical_compliance(draft: ResponseDraft, profile: dict[str, str]):
    doc = _new_doc(profile)
    doc.add_heading(f"Design Compliance for {draft.title}", level=1)
    add_rich(doc.add_paragraph(), f"Ref: {draft.rfq_number}    Due date: {draft.due_date}")
    add_rich(doc.add_paragraph(), f"Customer: {draft.buyer_name}")
    for section in draft.sections:
        doc.add_heading(section.heading, level=2)
        _table(doc, ["Sl. No", "Description", "Rug-Rel Compliance"],
               [[c.ref, c.requirement, _compliance_text(c.status, c.response)] for c in section.clauses])
    return _finish(doc)


def build_compliance_statement(draft: ResponseDraft, profile: dict[str, str]):
    if not draft.compliance_form_rows:
        return None
    doc = _new_doc(profile)
    doc.add_heading(draft.compliance_form_title or "Compliance Statement", level=1)
    add_rich(doc.add_paragraph(), f"RFQ No: {draft.rfq_number}    Due date: {draft.due_date}")
    bidder = (f"{fact(profile, 'company_name')}, {fact(profile, 'address')}. "
              f"Contact: {fact(profile, 'authorised_signatory')}, {fact(profile, 'email')}, "
              f"{fact(profile, 'phone')}. GSTIN: {fact(profile, 'gstin')}")
    _table(doc, ["Name of the bidder", ""], [["Firm name, address, contact", bidder]])
    doc.add_paragraph()
    _table(doc, ["S.No.", "Description of Terms", "Acceptance for Compliance (Y/N), deviation if any"],
           [[r.sno, r.term, r.response] for r in draft.compliance_form_rows])
    doc.add_paragraph("Note: To be provided on letterhead.")
    _signature(doc, profile, date.today())
    return _finish(doc)


def build_declarations(draft: ResponseDraft, profile: dict[str, str], today: date):
    doc = _new_doc(profile)
    doc.add_heading("Declarations", level=1)
    company, address = fact(profile, "company_name"), fact(profile, "address")
    if "mlc" in draft.declarations_needed:
        doc.add_heading("Self-Certification for Local Content", level=2)
        add_rich(doc.add_paragraph(), f"Tender Ref. No.: {draft.rfq_number}    Date: {today:%d.%m.%Y}")
        add_rich(doc.add_paragraph(), f"To: {draft.buyer_name}, {draft.buyer_address}")
        add_rich(doc.add_paragraph(),
                 f"In consideration of the above referred Tender issued by {draft.buyer_name}, we, M/s {company} "
                 f"of {address}, certify that we have offered the products with local content of "
                 f"{fact(profile, 'local_content_percent')}%.")
        add_rich(doc.add_paragraph(),
                 f"Details of the location(s) at which the local value addition is made: "
                 f"{fact(profile, 'value_addition_location')}")
        doc.add_paragraph("We further certify that, in case we are awarded an order against this tender, the "
                          "supplies against such order will comply with the above indicated Minimum Local Content.")
        _signature(doc, profile, today)
    if "land_border" in draft.declarations_needed:
        doc.add_heading("Declaration: Restrictions under Rule 144(xi) of GFR 2017", level=2)
        add_rich(doc.add_paragraph(), f"Tender Ref. No.: {draft.rfq_number}")
        add_rich(doc.add_paragraph(),
                 f"We, M/s {company}, have read the clause regarding restrictions on procurement from a bidder "
                 "of a country which shares a land border with India. We certify that this bidder is not from "
                 "such a country and does not collaborate with any entity from such a country, and that this "
                 "bidder fulfils all requirements in this regard and is eligible to be considered.")
        _signature(doc, profile, today)
    if "mse" in draft.declarations_needed:
        doc.add_heading("MSE Declaration", level=2)
        add_rich(doc.add_paragraph(), f"Tender Ref. No.: {draft.rfq_number}")
        add_rich(doc.add_paragraph(),
                 f"We, M/s {company}, are registered as a {fact(profile, 'msme_category')} enterprise under "
                 f"Udyam Registration No. {fact(profile, 'udyam_number')}. Social category: "
                 f"{fact(profile, 'social_category')}. Women-owned: {fact(profile, 'women_owned')}. "
                 "Documentary evidence is enclosed.")
        _signature(doc, profile, today)
    return _finish(doc)


def build_prebid_queries(draft: ResponseDraft, profile: dict[str, str], today: date):
    doc = _new_doc(profile)
    add_rich(doc.add_paragraph(), f"Date: {today:%d.%m.%Y}")
    add_rich(doc.add_paragraph(), f"To,\n{draft.buyer_name}\n{draft.buyer_address}")
    add_rich(doc.add_paragraph(), f"Kind attention: {draft.buyer_contact}")
    sub = doc.add_paragraph()
    sub.add_run(f"Subject: Pre-bid clarifications: {draft.rfq_number}, {draft.title}").bold = True
    doc.add_paragraph("Dear Sir/Madam,")
    doc.add_paragraph("With reference to the above RFQ, we request clarification on the following points so that "
                      "our offer fully meets your requirement:")
    for i, q in enumerate(draft.prebid_queries, 1):
        add_rich(doc.add_paragraph(), f"{i}. {q.clause_ref}: {q.query}")
    if not draft.prebid_queries:
        doc.add_paragraph("[[No queries identified; delete this letter or add queries]]")
    add_rich(doc.add_paragraph(),
             f"We would also request an extension of the bid due date ({draft.due_date}) by "
             "[[number of weeks / delete if not needed]] to allow these clarifications to be incorporated.")
    doc.add_paragraph("Thanking you,")
    _signature(doc, profile, today)
    return _finish(doc)


def build_checklist(draft: ResponseDraft) -> str:
    lines = [f"# Submission checklist: {draft.rfq_number}", "", f"**{draft.title}**  ",
             f"Buyer: {draft.buyer_name}  ", f"Due: {draft.due_date}", "",
             "## Required by the RFQ", ""]
    lines += [f"- [ ] {d.document}: {d.notes} _({d.source})_" for d in draft.required_documents]
    lines += ["", "## Drafted by this tool (complete the highlighted placeholders)", ""]
    lines += [f"- [ ] {name}" for name in PACK_FILES]
    return "\n".join(lines) + "\n"
