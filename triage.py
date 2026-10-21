"""Bid triage: turn one bid email + attachments into an assessment card.

Usage: python triage.py <bid.msg | bid.eml | folder> [--model M] [--effort E] [--out DIR]
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

from bidtriage.analyzer import DEFAULT_EFFORT, DEFAULT_MODEL, AnalysisError, analyze
from bidtriage.attachments import PayloadTooLarge, to_content_blocks
from bidtriage.email_loader import load_bid
from bidtriage.render import render_html, render_markdown
from bidtriage.schema import BidAssessment

NOT_STATED = "not stated"


def output_dir(base: Path, a: BidAssessment, subject: str, today: date) -> Path:
    name = a.rfq_number if a.rfq_number.strip().lower() != NOT_STATED else subject
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60].rstrip("-") or "bid"
    return base / f"{today:%Y-%m-%d}_{slug}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assess a bid email and its documents.")
    parser.add_argument("path", help="Outlook .msg, .eml, or a folder with email.txt and attachments")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default=DEFAULT_EFFORT, choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--out", default="out", help="Output base directory (default: out)")
    args = parser.parse_args(argv)

    try:
        bid = load_bid(args.path)
        blocks, skipped = to_content_blocks(bid.attachments)
        print(f"Analysing '{bid.subject}' ({len(blocks)} documents) with {args.model}...", file=sys.stderr)
        assessment = analyze(bid, blocks, skipped, model=args.model, effort=args.effort)
    except (ValueError, PayloadTooLarge, AnalysisError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    today = date.today()
    out = output_dir(Path(args.out), assessment, bid.subject, today)
    out.mkdir(parents=True, exist_ok=True)
    (out / "card.md").write_text(render_markdown(assessment, skipped, bid.subject), encoding="utf-8")
    (out / "card.html").write_text(render_html(assessment, skipped, bid.subject), encoding="utf-8")
    data = assessment.model_dump(mode="json")
    data["skipped_files"] = [{"filename": s.filename, "reason": s.reason} for s in skipped]
    (out / "assessment.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    for name in ("card.md", "card.html", "assessment.json"):
        print(out / name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
