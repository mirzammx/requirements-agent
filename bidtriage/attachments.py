"""Turn bid attachments into Claude content blocks."""

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath

from bidtriage.models import Attachment

# The API rejects requests over 32 MB; leave headroom for the prompt text.
MAX_PAYLOAD_BYTES = 30 * 1024 * 1024
# The API's PDF page limit for one request.
MAX_PDF_PAGES = 600

SPREADSHEET_EXTS = {".xlsx", ".xlsm"}
TEXT_EXTS = {".csv", ".txt"}


@dataclass
class Skipped:
    filename: str
    reason: str


class PayloadTooLarge(Exception):
    pass


def to_content_blocks(attachments: list[Attachment]) -> tuple[list[dict], list[Skipped]]:
    blocks: list[dict] = []
    skipped: list[Skipped] = []
    pdf_pages = 0
    for att in attachments:
        ext = PurePath(att.filename).suffix.lower()
        if att.unreadable_reason:
            skipped.append(Skipped(att.filename, att.unreadable_reason))
        elif ext == ".pdf":
            # One unreadable PDF would make the API reject the whole request, so check first.
            problem, pages = _check_pdf(att.data)
            if problem:
                skipped.append(Skipped(att.filename, problem))
                continue
            pdf_pages += pages
            blocks.append(_pdf_block(att))
        elif ext in SPREADSHEET_EXTS:
            try:
                blocks.append({"type": "text", "text": _xlsx_text(att)})
            except Exception as exc:
                skipped.append(Skipped(att.filename, f"could not read: {exc}"))
        elif ext in TEXT_EXTS:
            text = att.data.decode("utf-8", errors="replace")
            blocks.append({"type": "text", "text": f"=== {att.filename} ===\n{text}"})
        else:
            skipped.append(Skipped(att.filename, f"unsupported file type {ext or '(none)'}"))
    if pdf_pages > MAX_PDF_PAGES:
        raise PayloadTooLarge(
            f"attached PDFs have {pdf_pages} pages in total, over the {MAX_PDF_PAGES}-page limit for one request"
        )
    _check_payload_size(attachments, blocks)
    return blocks, skipped


def _check_pdf(data: bytes) -> tuple[str | None, int]:
    """Return (reason the PDF can't be sent, or None; page count)."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            return "password-protected PDF", 0
        return None, len(reader.pages)
    except Exception as exc:
        return f"could not read: {exc}", 0


def _pdf_block(att: Attachment) -> dict:
    return {
        "type": "document",
        "source": {
            "type": "base64",
            "media_type": "application/pdf",
            "data": base64.b64encode(att.data).decode(),
        },
        "title": att.filename,
    }


def _xlsx_text(att: Attachment) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(BytesIO(att.data), read_only=True, data_only=True)
    try:
        sections = []
        for ws in wb.worksheets:
            rows = [
                "\t".join("" if cell is None else str(cell) for cell in row)
                for row in ws.iter_rows(values_only=True)
            ]
            sections.append(f"=== {att.filename} / sheet {ws.title} ===\n" + "\n".join(rows))
        return "\n\n".join(sections)
    finally:
        wb.close()


def _check_payload_size(attachments: list[Attachment], blocks: list[dict]) -> None:
    total = sum(
        len(b["source"]["data"]) if b["type"] == "document" else len(b["text"].encode())
        for b in blocks
    )
    if total > MAX_PAYLOAD_BYTES:
        sizes = ", ".join(f"{a.filename} ({len(a.data) / 1_048_576:.1f} MB)" for a in attachments)
        raise PayloadTooLarge(
            f"attachments total {total / 1_048_576:.1f} MB after encoding, over the "
            f"{MAX_PAYLOAD_BYTES / 1_048_576:.0f} MB limit for one request: {sizes}"
        )
