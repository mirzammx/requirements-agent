from io import BytesIO

import httpx
import pytest
from pypdf import PdfWriter

from bidtriage.gem import GemError, bid_numbers_in_pdf, fetch_gem_document, gem_document_link, is_gem_link


def test_document_link_from_bidassist_detail_url():
    assert gem_document_link("https://bidplus.gem.gov.in/bidding/bid/getBidResultView/9945635") \
        == "https://bidplus.gem.gov.in/showbidDocument/9945635"
    assert gem_document_link("https://bidplus.gem.gov.in/showbidDocument/12") == "https://bidplus.gem.gov.in/showbidDocument/12"
    assert gem_document_link("https://defproc.gov.in/nicgep/app?page=FrontEndViewTender") == ""
    assert gem_document_link("https://evil.example/bidding/bid/getBidResultView/9945635") == ""
    assert gem_document_link("") == ""


def _pdf_with_text(text: str) -> bytes:
    # A tiny real PDF whose first page contains `text`.
    from pypdf.generic import ContentStream, DecodedStreamObject, NameObject, DictionaryObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=100)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 10 Tf 10 50 Td ({text}) Tj ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _client(status=200, content=b"", ctype="application/pdf"):
    def handler(request):
        return httpx.Response(status, content=content, headers={"content-type": ctype})
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_is_gem_link():
    assert is_gem_link("https://bidplus.gem.gov.in/showbidDocument/8082649")
    assert not is_gem_link("https://evil.example/showbidDocument/8082649")
    assert not is_gem_link("https://bidplus.gem.gov.in/showbidDocument/8082649/../x")
    assert not is_gem_link("http://bidplus.gem.gov.in/showbidDocument/8082649")


def test_fetch_returns_pdf_bytes():
    pdf = _pdf_with_text("Bid Number GEM/2026/B/8082649")
    assert fetch_gem_document("https://bidplus.gem.gov.in/showbidDocument/1", client=_client(content=pdf)) == pdf


def test_fetch_rejects_non_pdf_and_errors():
    url = "https://bidplus.gem.gov.in/showbidDocument/1"
    with pytest.raises(GemError, match="not a PDF"):
        fetch_gem_document(url, client=_client(content=b"<html>login</html>", ctype="text/html"))
    with pytest.raises(GemError, match="503"):
        fetch_gem_document(url, client=_client(status=503))
    with pytest.raises(GemError, match="GeM document link"):
        fetch_gem_document("https://evil.example/x", client=_client())


def test_bid_numbers_in_pdf():
    assert bid_numbers_in_pdf(_pdf_with_text("Bid Number GEM/2025/B/6447105 details")) == ["GEM/2025/B/6447105"]
    assert bid_numbers_in_pdf(b"not a pdf") == []
