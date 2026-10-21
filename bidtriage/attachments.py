"""Turn bid attachments into Claude content blocks."""

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath

from bidtriage.models import Attachment

# The API rejects requests over 32 MB; leave headroom for the prompt text.
MAX_PAYLOAD_BYTES = 30 * 1024 * 1024

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
    for att in attachments:
        ext = PurePath(att.filename).suffix.lower()
        if ext == ".pdf":
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
    _check_payload_size(attachments, blocks)
    return blocks, skipped


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
