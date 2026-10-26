"""The one Claude call: bid + documents in, BidAssessment out.

This is the only module that knows about the model provider. To move to Azure
(Claude in Microsoft Foundry), swap the client construction in `analyze`.

The JSON schema is sent via `output_config.format` and the reply is validated
here rather than by the SDK's `output_format` helper. The helper validates each
text block as it closes, which raises on a truncated or refused block before
`stop_reason` can be checked, and before a server-side fallback model's
answer (which follows a `fallback` block) can be read.
"""

from datetime import date
from pathlib import Path
from typing import TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from bidtriage.attachments import Skipped
from bidtriage.models import Bid
from bidtriage.schema import BidAssessment

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "high"
MAX_TOKENS = 64000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
M = TypeVar("M", bound=BaseModel)


class AnalysisError(Exception):
    pass


def load_prompts() -> tuple[str, str]:
    """(system prompt, capability profile) from the prompts/ folder."""
    return (
        (PROMPTS_DIR / "system.md").read_text(encoding="utf-8"),
        (PROMPTS_DIR / "capability_profile.md").read_text(encoding="utf-8"),
    )


def system_text(system_prompt: str, profile: str) -> str:
    return f"{system_prompt}\n\n# Capability profile\n\n{profile}"


def user_text(bid: Bid, blocks: list[dict], skipped: list[Skipped], today: date) -> str:
    """The text that follows the documents: today's date, the email, and what is attached."""
    titles = [b["title"] for b in blocks if b.get("type") == "document"]
    titles += [b["text"].splitlines()[0].strip("= ") for b in blocks if b.get("type") == "text"]
    text = (
        f"Today's date: {today.isoformat()}\n\n"
        f"From: {bid.sender}\nDate: {bid.date}\nSubject: {bid.subject}\n\n"
        f"{bid.body}\n\n"
        f"Attached documents: {', '.join(titles) or 'none'}"
    )
    if skipped:
        text += (
            f"\nAttached but not readable by this tool: {', '.join(s.filename for s in skipped)}"
            " (do not report these as missing; ask the reviewer to check them)"
        )
    return text


def claude_request(system: str, blocks: list[dict], text: str, schema: type[BaseModel], *,
                   model: str, effort: str) -> dict:
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "output_config": {
            "effort": effort,
            "format": {"type": "json_schema", "schema": anthropic.transform_schema(schema.model_json_schema())},
        },
        "system": system,
        "messages": [{"role": "user", "content": [*blocks, {"type": "text", "text": text}]}],
        # Server-side refusal fallback: a declined request is re-run on another model.
        "extra_headers": {"anthropic-beta": FALLBACK_BETA},
        "extra_body": {"fallbacks": "default"},
    }


def build_request(bid: Bid, blocks: list[dict], skipped: list[Skipped], *, model: str, effort: str,
                  today: date, system_prompt: str, profile: str) -> dict:
    return claude_request(system_text(system_prompt, profile), blocks, user_text(bid, blocks, skipped, today),
                          BidAssessment, model=model, effort=effort)


def analyze(bid: Bid, blocks: list[dict], skipped: list[Skipped] | None = None, *, client=None,
            model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT,
            today: date | None = None) -> BidAssessment:
    system_prompt, profile = load_prompts()
    return call_claude(system_text(system_prompt, profile), blocks,
                       user_text(bid, blocks, skipped or [], today or date.today()), BidAssessment,
                       client=client, model=model, effort=effort)


def call_claude(system: str, blocks: list[dict], text: str, schema: type[M], *, client=None,
                model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT, label: str = "assessment") -> M:
    """One structured Claude call; returns `schema` validated, or raises AnalysisError."""
    request = claude_request(system, blocks, text, schema, model=model, effort=effort)
    client = client or anthropic.Anthropic()
    try:
        with client.messages.stream(**request) as stream:
            message = stream.get_final_message()
    except anthropic.APIStatusError as exc:
        raise AnalysisError(f"Claude API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise AnalysisError(f"could not reach the Claude API: {exc}") from exc
    except TypeError as exc:
        if "authentication" not in str(exc):
            raise
        raise AnalysisError(
            "no Claude API credentials found: set ANTHROPIC_API_KEY or run `ant auth login`"
        ) from exc
    if message.stop_reason in ("refusal", "max_tokens"):
        raise AnalysisError(f"Claude stopped with {message.stop_reason}; nothing written")
    try:
        return schema.model_validate_json(_final_text(message.content))
    except ValidationError as exc:
        raise AnalysisError(f"Claude's reply was not a valid {label}; nothing written ({exc})") from exc


def _final_text(content: list) -> str:
    """Text of the answering model: everything after the last fallback block, if any."""
    last_fallback = max((i for i, b in enumerate(content) if b.type == "fallback"), default=-1)
    return "".join(b.text for b in content[last_fallback + 1 :] if b.type == "text")
