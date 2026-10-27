"""Draft the response pack for a bid that has been triaged and approved.

Usage: python draft.py <bid> --card out/<bid-dir> [--provider gemini] [--model M] [--effort E]
Writes <bid-dir>/response/: Technical_Compliance.docx, Compliance_Statement.docx, Price_Bid.xlsx,
Declarations.docx, PreBid_Queries.docx, Checklist.md, draft.json.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from bidtriage.analyzer import AnalysisError
from bidtriage.attachments import PayloadTooLarge, to_content_blocks
from bidtriage.docx_out import (
    all_text,
    build_checklist,
    build_compliance_statement,
    build_declarations,
    build_prebid_queries,
    build_technical_compliance,
    count_placeholders,
)
from bidtriage.draft_schema import ResponseDraft
from bidtriage.drafter import draft_response
from bidtriage.email_loader import load_bid
from bidtriage.guards import apply_guards
from bidtriage.profile import load_profile
from bidtriage.schema import BidAssessment
from bidtriage.xlsx_out import build_price_bid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Draft response documents for an approved bid.")
    parser.add_argument("path", help="The bid: Outlook .msg, .eml, or a folder (as for triage.py)")
    parser.add_argument("--card", required=True, help="The triage output folder containing assessment.json")
    parser.add_argument("--provider", default="claude", choices=["claude", "gemini"])
    parser.add_argument("--model")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"],
                        help="default: high for Claude; low for Gemini, whose per-request time limit a full "
                             "high-effort draft exceeds")
    parser.add_argument("--from-draft", help="Re-render documents from a saved draft.json (no model call)")
    args = parser.parse_args(argv)

    try:
        summary = run_draft(args.path, Path(args.card), provider=args.provider, model=args.model,
                            effort=args.effort, from_draft=Path(args.from_draft) if args.from_draft else None)
    except PackWriteError as exc:
        print(f"error: could not write the documents ({exc.__cause__}). Close any open copies in Word/Excel, then "
              f"re-run with --from-draft {exc.draft_path} to regenerate them without a new model call.",
              file=sys.stderr)
        return 1
    except (OSError, ValueError, ValidationError, PayloadTooLarge, AnalysisError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out = Path(args.card) / "response"
    for name, count in summary.items():
        print(f"{out / name}: {_describe(name, count)}")
    return 0


class PackWriteError(Exception):
    """The draft was obtained (and saved) but writing the documents failed."""

    def __init__(self, draft_path: Path, cause: Exception):
        super().__init__(f"could not write the documents ({cause}); the draft is saved at {draft_path} and the "
                         "documents can be rebuilt from it without a new model call")
        self.draft_path = draft_path


def _describe(name: str, count: int | None) -> str:
    if count is None:
        return "not needed (no buyer compliance form in the RFQ)" if name.endswith(".docx") else "written"
    return f"{count} lines to price" if name.endswith(".xlsx") else f"{count} placeholders"


def run_draft(path, card_dir: Path, *, provider: str = "claude", model: str | None = None,
              effort: str | None = None, from_draft: Path | None = None) -> dict[str, int | None]:
    """Draft (or re-render) the response pack into card_dir/response; returns file -> placeholder count."""
    effort = effort or ("low" if provider == "gemini" else "high")
    out = Path(card_dir) / "response"
    profile = load_profile()
    if from_draft:
        draft = apply_guards(ResponseDraft.model_validate_json(Path(from_draft).read_text(encoding="utf-8")),
                             profile)
    else:
        assessment_file = Path(card_dir) / "assessment.json"
        if not assessment_file.is_file():
            raise ValueError(f"{assessment_file} not found: run triage on this bid first")
        assessment = BidAssessment.model_validate_json(assessment_file.read_text(encoding="utf-8"))
        bid = load_bid(path)
        blocks, skipped = to_content_blocks(bid.attachments)
        print(f"Drafting response for '{bid.subject}' with {provider}...", file=sys.stderr)
        draft = draft_response(bid, blocks, skipped, assessment, provider=provider, model=model,
                               effort=effort, profile=profile)
        # Save the paid-for draft before anything else can fail.
        out.mkdir(parents=True, exist_ok=True)
        (out / "draft.json").write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    try:
        return _write_pack(draft, profile, out)
    except (OSError, ValueError) as exc:
        raise PackWriteError(out / "draft.json", exc) from exc


def _write_pack(draft: ResponseDraft, profile: dict[str, str], out: Path) -> dict[str, int | None]:
    today = date.today()
    out.mkdir(parents=True, exist_ok=True)
    summary: dict[str, int | None] = {}
    docs = {
        "Technical_Compliance.docx": build_technical_compliance(draft, profile),
        "Compliance_Statement.docx": build_compliance_statement(draft, profile),
        "Declarations.docx": build_declarations(draft, profile, today),
        "PreBid_Queries.docx": build_prebid_queries(draft, profile, today),
    }
    for name, doc in docs.items():
        if doc is None:
            # Remove any copy from an earlier draft so an outdated form cannot be submitted.
            (out / name).unlink(missing_ok=True)
            summary[name] = None
            continue
        doc.save(out / name)
        summary[name] = count_placeholders(all_text(doc))
    build_price_bid(draft).save(out / "Price_Bid.xlsx")
    summary["Price_Bid.xlsx"] = len(draft.price_lines)
    (out / "Checklist.md").write_text(build_checklist(draft), encoding="utf-8")
    summary["Checklist.md"] = None
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    sys.exit(main())
