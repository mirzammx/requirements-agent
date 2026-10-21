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


class _FakeAtt:
    def __init__(self, name, data=None, att_type=None, data_error=None):
        self.longFilename = name
        self.shortFilename = None
        self.type = att_type
        self._data, self._error = data, data_error

    @property
    def data(self):
        if self._error:
            raise self._error
        return self._data


def test_msg_cloud_embedded_and_broken_attachments_do_not_crash(tmp_path, monkeypatch):
    import extract_msg
    from extract_msg.enums import AttachmentType

    from bidtriage.attachments import to_content_blocks

    atts = [
        _FakeAtt("rfq.csv", b"a,b", AttachmentType.DATA),
        _FakeAtt("Tender pack", att_type=AttachmentType.WEB, data_error=NotImplementedError("web")),
        _FakeAtt("Fwd RFQ.msg", data=object(), att_type=AttachmentType.MSG),
        _FakeAtt("odd.bin", data=None, att_type=AttachmentType.UNSUPPORTED),
    ]

    class FakeMsg:
        def __init__(self, path, **kwargs):
            self.subject, self.sender, self.date, self.body = "S", "F", "D", "B"
            self.attachments = atts

        def close(self):
            pass

    monkeypatch.setattr(extract_msg, "Message", FakeMsg)
    bid = load_bid(tmp_path / "bid.msg")

    assert [a.filename for a in bid.attachments] == ["rfq.csv", "Tender pack", "Fwd RFQ.msg", "odd.bin"]
    blocks, skipped = to_content_blocks(bid.attachments)
    assert len(blocks) == 1
    reasons = {s.filename: s.reason for s in skipped}
    assert "cloud" in reasons["Tender pack"]
    assert "forwarded email" in reasons["Fwd RFQ.msg"]
    assert "could not extract" in reasons["odd.bin"]
