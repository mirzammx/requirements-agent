"""Draft the response pack for a bid that has been triaged and approved.

Usage: python draft.py <bid> --card out/<bid-dir> [--provider gemini] [--model M] [--effort E]
Writes <bid-dir>/response/: Technical_Compliance.docx, Compliance_Statement.docx, Price_Bid.xlsx,
Declarations.docx, PreBid_Queries.docx, Checklist.md, draft.json.
"""

import argparse
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
from bidtriage.drafter import draft_response
from bidtriage.email_loader import load_bid
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
    args = parser.parse_args(argv)
    effort = args.effort or ("low" if args.provider == "gemini" else "high")

    card = Path(args.card)
    try:
        assessment_file = card / "assessment.json"
        if not assessment_file.is_file():
            raise ValueError(f"{assessment_file} not found: run triage.py on this bid first")
        assessment = BidAssessment.model_validate_json(assessment_file.read_text(encoding="utf-8"))
        bid = load_bid(args.path)
        blocks, skipped = to_content_blocks(bid.attachments)
        print(f"Drafting response for '{bid.subject}' with {args.provider}...", file=sys.stderr)
        profile = load_profile()
        draft = draft_response(bid, blocks, skipped, assessment, provider=args.provider, model=args.model,
                               effort=effort, profile=profile)
    except (ValueError, ValidationError, PayloadTooLarge, AnalysisError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    today = date.today()
    out = card / "response"
    out.mkdir(parents=True, exist_ok=True)
    docs = {
        "Technical_Compliance.docx": build_technical_compliance(draft, profile),
        "Compliance_Statement.docx": build_compliance_statement(draft, profile),
        "Declarations.docx": build_declarations(draft, profile, today),
        "PreBid_Queries.docx": build_prebid_queries(draft, profile, today),
    }
    for name, doc in docs.items():
        if doc is None:
            print(f"{out / name}: not needed (no buyer compliance form in the RFQ)")
            continue
        doc.save(out / name)
        print(f"{out / name}: {count_placeholders(all_text(doc))} placeholders")
    build_price_bid(draft).save(out / "Price_Bid.xlsx")
    print(f"{out / 'Price_Bid.xlsx'}: {len(draft.price_lines)} lines to price")
    (out / "Checklist.md").write_text(build_checklist(draft), encoding="utf-8")
    (out / "draft.json").write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    print(out / "Checklist.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
