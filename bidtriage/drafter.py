"""Draft a bid response: one structured model call, then the code guards."""

import json
from datetime import date

from bidtriage.analyzer import DEFAULT_MODEL, PROMPTS_DIR, call_claude, user_text
from bidtriage.attachments import Skipped
from bidtriage.draft_schema import ResponseDraft
from bidtriage.gemini_analyzer import DEFAULT_GEMINI_MODEL, call_gemini
from bidtriage.guards import apply_guards
from bidtriage.models import Bid
from bidtriage.profile import load_profile
from bidtriage.schema import BidAssessment

PROVIDERS = {"claude": call_claude, "gemini": call_gemini}
DEFAULT_MODELS = {"claude": DEFAULT_MODEL, "gemini": DEFAULT_GEMINI_MODEL}


def draft_user_text(bid: Bid, blocks: list[dict], skipped: list[Skipped], assessment: BidAssessment,
                    profile: dict[str, str], today: date) -> str:
    return (
        f"{user_text(bid, blocks, skipped, today)}\n\n"
        "# Triage assessment of this bid\n\n"
        f"{assessment.model_dump_json(indent=2)}\n\n"
        "# Rug-Rel company profile (empty value = unknown, never assert it)\n\n"
        f"{json.dumps(profile, indent=2, ensure_ascii=False)}\n\n"
        "Draft the response for this bid."
    )


def draft_response(bid: Bid, blocks: list[dict], skipped: list[Skipped], assessment: BidAssessment, *,
                   provider: str = "claude", model: str | None = None, effort: str = "high",
                   today: date | None = None, profile: dict[str, str] | None = None,
                   client=None) -> ResponseDraft:
    profile = profile if profile is not None else load_profile()
    system = (PROMPTS_DIR / "draft_system.md").read_text(encoding="utf-8")
    text = draft_user_text(bid, blocks, skipped, assessment, profile, today or date.today())
    draft = PROVIDERS[provider](system, blocks, text, ResponseDraft, client=client,
                                model=model or DEFAULT_MODELS[provider], effort=effort, label="response draft")
    return apply_guards(draft, profile)
