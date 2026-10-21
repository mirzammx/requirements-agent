from email.message import EmailMessage

import pytest

from bidtriage.email_loader import load_bid

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def test_load_eml_with_attachments(tmp_path):
    msg = EmailMessage()
    msg["Subject"] = "AHRU Power Supply Requirement- HAL HYDERABAD"
    msg["From"] = "imran khan <imran.khan@rugrel.com>"
    msg["Date"] = "Wed, 07 Oct 2026 18:06:00 +0530"
    msg.set_content("Check the feasibility.")
    msg.add_attachment(b"%PDF-1.4 fake", maintype="application", subtype="pdf", filename="rfq.pdf")
    maintype, subtype = XLSX_MIME.split("/")
    msg.add_attachment(b"PK fake xlsx", maintype=maintype, subtype=subtype, filename="qty.xlsx")
    eml_path = tmp_path / "bid.eml"
    eml_path.write_bytes(msg.as_bytes())

    bid = load_bid(eml_path)

    assert bid.subject == "AHRU Power Supply Requirement- HAL HYDERABAD"
    assert "imran.khan@rugrel.com" in bid.sender
    assert "Check the feasibility." in bid.body
    assert [a.filename for a in bid.attachments] == ["rfq.pdf", "qty.xlsx"]
    assert bid.attachments[0].data == b"%PDF-1.4 fake"


def test_load_folder_reads_email_txt_and_files(tmp_path):
    (tmp_path / "email.txt").write_text("Subject: Test bid\n\nBody line", encoding="utf-8")
    (tmp_path / "a.pdf").write_bytes(b"%PDF")
    (tmp_path / "b.csv").write_bytes(b"x,y")

    bid = load_bid(tmp_path)

    assert bid.subject == "Test bid"
    assert "Body line" in bid.body
    assert sorted(a.filename for a in bid.attachments) == ["a.pdf", "b.csv"]


def test_load_folder_without_email_txt(tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF")

    bid = load_bid(tmp_path)

    assert bid.body == ""
    assert bid.subject == tmp_path.name
    assert [a.filename for a in bid.attachments] == ["a.pdf"]


def test_unknown_path_type_raises(tmp_path):
    p = tmp_path / "bid.docx"
    p.write_bytes(b"x")
    with pytest.raises(ValueError):
        load_bid(p)
