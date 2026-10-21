"""The one Claude call: bid + documents in, BidAssessment out.

This is the only module that knows about the model provider. To move to Azure
(Claude in Microsoft Foundry), swap the client construction in `analyze`.
"""

from datetime import date
from pathlib import Path

import anthropic

from bidtriage.models import Bid
from bidtriage.schema import BidAssessment

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
MAX_TOKENS = 64000
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnalysisError(Exception):
    pass


def build_request(bid: Bid, blocks: list[dict], *, model: str, effort: str, today: date,
                  system_prompt: str, profile: str) -> dict:
    titles = [b["title"] for b in blocks if b.get("type") == "document"]
    titles += [b["text"].splitlines()[0].strip("= ") for b in blocks if b.get("type") == "text"]
    text = (
        f"Today's date: {today.isoformat()}\n\n"
        f"From: {bid.sender}\nDate: {bid.date}\nSubject: {bid.subject}\n\n"
        f"{bid.body}\n\n"
        f"Attached documents: {', '.join(titles) or 'none'}"
    )
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "output_config": {"effort": effort},
        "system": f"{system_prompt}\n\n# Capability profile\n\n{profile}",
        "messages": [{"role": "user", "content": [*blocks, {"type": "text", "text": text}]}],
        # Server-side refusal fallback: a declined request is re-run on another model.
        "extra_headers": {"anthropic-beta": FALLBACK_BETA},
        "extra_body": {"fallbacks": "default"},
    }


def analyze(bid: Bid, blocks: list[dict], *, client=None, model: str = DEFAULT_MODEL,
            effort: str = DEFAULT_EFFORT, today: date | None = None) -> BidAssessment:
    request = build_request(
        bid, blocks, model=model, effort=effort, today=today or date.today(),
        system_prompt=(PROMPTS_DIR / "system.md").read_text(encoding="utf-8"),
        profile=(PROMPTS_DIR / "capability_profile.md").read_text(encoding="utf-8"),
    )
    client = client or anthropic.Anthropic()
    try:
        with client.messages.stream(**request, output_format=BidAssessment) as stream:
            message = stream.get_final_message()
    except anthropic.APIStatusError as exc:
        raise AnalysisError(f"Claude API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise AnalysisError(f"could not reach the Claude API: {exc}") from exc
    if message.stop_reason in ("refusal", "max_tokens"):
        raise AnalysisError(f"Claude stopped with {message.stop_reason}; no card written")
    if message.parsed_output is None:
        raise AnalysisError("Claude returned no parsable assessment; no card written")
    return message.parsed_output
