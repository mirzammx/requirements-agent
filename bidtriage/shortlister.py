"""Classify BidAssist tenders: SBU-2 power candidates, other product lines, or not relevant."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel

from bidtriage.analyzer import DEFAULT_MODEL, PROMPTS_DIR, AnalysisError, call_claude
from bidtriage.bidassist import Tender, parse_date
from bidtriage.gemini_analyzer import DEFAULT_GEMINI_MODEL, call_gemini

PROVIDERS = {"claude": call_claude, "gemini": call_gemini}
DEFAULT_MODELS = {"claude": DEFAULT_MODEL, "gemini": DEFAULT_GEMINI_MODEL}
BATCH_SIZE = 60


class RowVerdict(BaseModel):
    tender_id: str
    category: Literal["sbu2_power", "other_product_line", "not_relevant"]
    route_to: str
    confidence: Literal["high", "medium", "low"]
    reason: str


class Verdicts(BaseModel):
    verdicts: list[RowVerdict]


@dataclass
class Shortlisted:
    tender: Tender
    category: str          # sbu2_power / other_product_line / not_relevant / manual_check
    route_to: str
    confidence: str
    reason: str
    days_left: int | None


def batch_text(batch: list[Tender]) -> str:
    lines = ["Classify each of these tenders (one per line):", ""]
    for t in batch:
        parts = [t.tender_id, t.authority, t.summary]
        if t.description and t.description != t.summary:
            parts.append(f"description: {t.description}")
        parts += [f"keyword: {t.keyword}", f"value: {t.amount}", f"location: {t.location}"]
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _system() -> str:
    return ((PROMPTS_DIR / "shortlist_system.md").read_text(encoding="utf-8")
            + "\n\n# Capability profile\n\n"
            + (PROMPTS_DIR / "capability_profile.md").read_text(encoding="utf-8"))


def classify(tenders: list[Tender], *, provider: str = "claude", model: str | None = None, effort: str = "low",
             today: date | None = None, client=None, batch_size: int = BATCH_SIZE) -> list[Shortlisted]:
    today = today or date.today()
    call = PROVIDERS[provider]
    system = _system()
    verdicts: dict[str, RowVerdict] = {}
    failed: dict[str, str] = {}   # tender_id -> error of the batch it was in
    errors: list[AnalysisError] = []
    batches = [tenders[i:i + batch_size] for i in range(0, len(tenders), batch_size)]
    for batch in batches:
        try:
            result = call(system, [], batch_text(batch), Verdicts, client=client,
                          model=model or DEFAULT_MODELS[provider], effort=effort, label="shortlist")
        except AnalysisError as exc:
            # Keep the batches that worked; this batch's rows go to manual check.
            errors.append(exc)
            failed.update({t.tender_id: str(exc) for t in batch})
            continue
        wanted = {t.tender_id for t in batch}
        verdicts.update({v.tender_id: v for v in result.verdicts if v.tender_id in wanted})
    if batches and len(errors) == len(batches):
        raise errors[0]

    out = []
    for t in tenders:
        closing = parse_date(t.closing_date)
        days_left = (closing - today).days if closing else None
        v = verdicts.get(t.tender_id)
        if v is None:
            reason = (f"Batch failed ({failed[t.tender_id]}); check by hand or re-run." if t.tender_id in failed
                      else "Not classified by the model; check by hand.")
            out.append(Shortlisted(t, "manual_check", "", "", reason, days_left))
        else:
            out.append(Shortlisted(t, v.category, v.route_to, v.confidence, v.reason, days_left))
    return out
