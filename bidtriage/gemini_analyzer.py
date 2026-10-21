"""Gemini alternative to analyzer.py, for proof-of-concept testing on the free tier.

Same prompts, same BidAssessment output. Gemini has no per-document title, so
each PDF is preceded by a text label naming the file; the model cites from that.
Note: free-tier requests may be used by Google to improve its products.
"""

import base64
from datetime import date

from pydantic import ValidationError

from bidtriage.analyzer import AnalysisError, load_prompts, system_text, user_text
from bidtriage.attachments import Skipped
from bidtriage.models import Bid
from bidtriage.schema import BidAssessment

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
# Gemini's limit for a request with inline file data is 20 MB.
MAX_INLINE_BYTES = 19 * 1024 * 1024
OK_FINISH = {"STOP", "FINISH_REASON_UNSPECIFIED"}


def build_gemini_request(bid: Bid, blocks: list[dict], skipped: list[Skipped], *, model: str, effort: str,
                         today: date, system_prompt: str, profile: str) -> dict:
    from google.genai import types

    parts = []
    for b in blocks:
        if b["type"] == "document":
            parts.append(types.Part.from_text(text=f"=== Document: {b['title']} ==="))
            parts.append(types.Part.from_bytes(data=base64.b64decode(b["source"]["data"]),
                                               mime_type=b["source"]["media_type"]))
        else:
            parts.append(types.Part.from_text(text=b["text"]))
    parts.append(types.Part.from_text(text=user_text(bid, blocks, skipped, today)))
    level = {"low": "LOW", "medium": "MEDIUM"}.get(effort, "HIGH")
    config = types.GenerateContentConfig(
        system_instruction=system_text(system_prompt, profile),
        response_mime_type="application/json",
        response_json_schema=BidAssessment.model_json_schema(),
        thinking_config=types.ThinkingConfig(thinking_level=level),
    )
    return {"model": model, "contents": parts, "config": config}


def analyze_gemini(bid: Bid, blocks: list[dict], skipped: list[Skipped] | None = None, *, client=None,
                   model: str = DEFAULT_GEMINI_MODEL, effort: str = "high",
                   today: date | None = None) -> BidAssessment:
    size = sum(len(b["source"]["data"]) * 3 // 4 if b["type"] == "document" else len(b["text"].encode())
               for b in blocks)
    if size > MAX_INLINE_BYTES:
        raise AnalysisError(f"attachments ({size / 1_048_576:.1f} MB) are too large for one Gemini request "
                            f"(limit {MAX_INLINE_BYTES / 1_048_576:.0f} MB)")
    system_prompt, profile = load_prompts()
    request = build_gemini_request(bid, blocks, skipped or [], model=model, effort=effort,
                                   today=today or date.today(), system_prompt=system_prompt, profile=profile)
    from google import genai
    from google.genai import errors

    try:
        client = client or genai.Client()
        response = client.models.generate_content(**request)
    except errors.APIError as exc:
        raise AnalysisError(f"Gemini API error {exc.code}: {exc.message}") from exc
    except ValueError as exc:
        if "API key" not in str(exc):
            raise
        raise AnalysisError("no Gemini API key found: set GEMINI_API_KEY (get one at aistudio.google.com)") from exc

    if not response.candidates:
        raise AnalysisError(f"Gemini returned no answer ({response.prompt_feedback}); no card written")
    finish = response.candidates[0].finish_reason
    finish_name = getattr(finish, "name", str(finish))
    if finish_name not in OK_FINISH:
        raise AnalysisError(f"Gemini stopped with {finish_name}; no card written")
    try:
        return BidAssessment.model_validate_json(response.text or "")
    except ValidationError as exc:
        raise AnalysisError(f"Gemini's reply was not a valid assessment; no card written ({exc})") from exc
