import base64
from io import BytesIO

import openpyxl
import pytest
from pypdf import PdfWriter

from bidtriage import attachments
from bidtriage.attachments import PayloadTooLarge, to_content_blocks
from bidtriage.models import Attachment

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Price"
    ws.append(["Item", "Qty"])
    ws.append(["PSM", 4])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _pdf_bytes(pages: int = 1, password: str | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    if password:
        writer.encrypt(password)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_pdf_becomes_document_block():
    pdf = _pdf_bytes()
    blocks, skipped = to_content_blocks([Attachment("rfq.pdf", pdf, "application/pdf")])
    assert blocks[0]["type"] == "document"
    assert blocks[0]["source"] == {
        "type": "base64",
        "media_type": "application/pdf",
        "data": base64.b64encode(pdf).decode(),
    }
    assert blocks[0]["title"] == "rfq.pdf"
    assert skipped == []


def test_xlsx_becomes_text_table():
    blocks, _ = to_content_blocks([Attachment("price.xlsx", _xlsx_bytes(), XLSX_MIME)])
    assert blocks[0]["type"] == "text"
    assert "=== price.xlsx / sheet Price ===" in blocks[0]["text"]
    assert "PSM\t4" in blocks[0]["text"]


def test_csv_and_txt_become_text():
    blocks, _ = to_content_blocks([Attachment("q.csv", b"a,b\n1,2", "text/csv")])
    assert "=== q.csv ===" in blocks[0]["text"]
    assert "1,2" in blocks[0]["text"]


def test_unsupported_types_are_skipped():
    _, skipped = to_content_blocks([
        Attachment("spec.docx", b"x", ""),
        Attachment("fwd.msg", b"", "message/rfc822"),
        Attachment("photo.jpg", b"x", "image/jpeg"),
    ])
    assert [s.filename for s in skipped] == ["spec.docx", "fwd.msg", "photo.jpg"]
    assert all(s.reason for s in skipped)


def test_corrupt_xlsx_is_skipped_with_reason():
    blocks, skipped = to_content_blocks([Attachment("bad.xlsx", b"not a zip", "")])
    assert blocks == []
    assert skipped[0].filename == "bad.xlsx"
    assert "could not read" in skipped[0].reason


def test_payload_over_limit_raises(monkeypatch):
    monkeypatch.setattr(attachments, "MAX_PAYLOAD_BYTES", 10)
    with pytest.raises(PayloadTooLarge, match="big.pdf"):
        to_content_blocks([Attachment("big.pdf", _pdf_bytes(), "application/pdf")])


def test_encrypted_pdf_is_skipped_not_sent():
    blocks, skipped = to_content_blocks([Attachment("locked.pdf", _pdf_bytes(password="x"), "application/pdf")])
    assert blocks == []
    assert skipped[0].filename == "locked.pdf"
    assert "password-protected" in skipped[0].reason


def test_corrupt_pdf_is_skipped_not_sent():
    blocks, skipped = to_content_blocks([Attachment("broken.pdf", b"not a pdf at all", "application/pdf")])
    assert blocks == []
    assert "could not read" in skipped[0].reason


def test_total_pdf_pages_over_limit_raises(monkeypatch):
    monkeypatch.setattr(attachments, "MAX_PDF_PAGES", 3)
    with pytest.raises(PayloadTooLarge, match="pages"):
        to_content_blocks([Attachment("a.pdf", _pdf_bytes(2), ""), Attachment("b.pdf", _pdf_bytes(2), "")])
