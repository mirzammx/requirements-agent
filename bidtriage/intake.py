"""Decide what an incoming mail is: a BidAssist alert to screen, or a bid to triage.

A BidAssist alert carries "<alert>-Tender List_<date>.xlsx" attachments. Only the alerts listed in
prompts/intake.toml `screen_alerts` are screened; the rest (e.g. "My Preference") are ignored for now.
"""

import re
import tomllib
from pathlib import Path

from bidtriage.models import Attachment, Bid

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "intake.toml"
DEFAULTS = {
    "screen_alerts": ["Power supply"],
    "mahadevan_email": "mahadevan.velvalli@rugrel.com",
    "signature": "On behalf of Mahadevan, SBU-2 (Power Electronics), Rug-Rel Components & Systems",
}
TENDER_LIST = re.compile(r"^(?P<alert>.+?)\s*-\s*Tender List.*\.xlsx$", re.I)


def load_intake_settings(path: Path | str | None = None) -> dict:
    path = Path(path) if path else SETTINGS_PATH
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return {**DEFAULTS, **{k: v for k, v in data.items() if k in DEFAULTS}}


def alert_name(filename: str) -> str | None:
    m = TENDER_LIST.match(filename.strip())
    return m.group("alert").strip() if m else None


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def classify_mail(bid: Bid, settings: dict) -> tuple[str, list[Attachment], list[str]]:
    """("bidassist", attachments to screen, ignored file names) or ("bid", [], [])."""
    lists = [a for a in bid.attachments if alert_name(a.filename)]
    if not lists:
        return "bid", [], []
    wanted = {_norm(n) for n in settings["screen_alerts"]}
    screen = [a for a in lists if _norm(alert_name(a.filename)) in wanted]
    ignored = [a.filename for a in lists if a not in screen]
    return "bidassist", screen, ignored
