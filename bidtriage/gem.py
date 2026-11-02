"""Download a GeM bid document, and check which bid it really is.

GeM's document links (https://bidplus.gem.gov.in/showbidDocument/<n>) use an internal number that
is NOT the bid number, so a wrong link would silently bring in another tender. The number comes from
BidAssist's "Tender Detail Url" (.../getBidResultView/<n>) or from a link BD pastes. bid_numbers_in_pdf()
lets the caller check the PDF names the expected bid. One request per user action; no crawling.
"""

import re
from io import BytesIO

import httpx

GEM_LINK = re.compile(r"^https://bidplus\.gem\.gov\.in/showbidDocument/\d+$")
GEM_PAGE = re.compile(r"^https://bidplus\.gem\.gov\.in/(?:bidding/bid/getBidResultView|showbidDocument)/(\d+)$")
BID_NUMBER = re.compile(r"GEM/\d{4}/B/\d+")
MAX_BYTES = 30 * 1024 * 1024
USER_AGENT = "RugRel-BidDesk/1.0 (single document download for bid evaluation)"


class GemError(Exception):
    pass


def is_gem_link(url: str) -> bool:
    return bool(GEM_LINK.match(url.strip()))


def gem_document_link(page_url: str) -> str:
    """The bid document link for a GeM bid page (as in BidAssist's export), or "" if it is not a GeM bid."""
    m = GEM_PAGE.match((page_url or "").strip())
    return f"https://bidplus.gem.gov.in/showbidDocument/{m.group(1)}" if m else ""


def fetch_gem_document(url: str, *, client: httpx.Client | None = None) -> bytes:
    url = url.strip()
    if not is_gem_link(url):
        raise GemError("That is not a GeM document link. It should look like "
                       "https://bidplus.gem.gov.in/showbidDocument/1234567")
    own = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=False, headers={"User-Agent": USER_AGENT})
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        raise GemError(f"Could not reach GeM ({exc}). Try again, or download the PDF and upload it.") from exc
    finally:
        if own:
            client.close()
    if response.status_code != 200:
        raise GemError(f"GeM answered {response.status_code}. Try again later, or download the PDF and upload it.")
    data = response.content
    if not data.startswith(b"%PDF") or "pdf" not in response.headers.get("content-type", "").lower():
        raise GemError("GeM did not send a PDF (it is not a PDF; maybe a login or error page). "
                       "Download the PDF yourself and upload it.")
    if len(data) > MAX_BYTES:
        raise GemError("The GeM document is too large.")
    return data


def bid_numbers_in_pdf(data: bytes) -> list[str]:
    """GeM bid numbers printed on the first pages of the PDF (empty if unreadable)."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(data))
        text = " ".join((page.extract_text() or "") for page in reader.pages[:3])
    except Exception:
        return []
    found = []
    for n in BID_NUMBER.findall(text):
        if n not in found:
            found.append(n)
    return found
