"""Screen BidAssist alert exports and produce a daily shortlist.

Usage: python shortlist.py "<alert>-Tender List_<date>.xlsx" [more.xlsx ...] [--provider gemini]
Writes out/shortlist_<date>/: digest.html, shortlist.xlsx (with a Decision column), shortlist.json.
"""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from bidtriage.analyzer import AnalysisError
from bidtriage.bidassist import read_tender_lists
from bidtriage.shortlist_out import build_tracker, render_digest
from bidtriage.shortlister import classify


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Screen BidAssist tender lists for SBU-2.")
    parser.add_argument("paths", nargs="+", help="BidAssist Tender List .xlsx files")
    parser.add_argument("--provider", default="claude", choices=["claude", "gemini"])
    parser.add_argument("--model")
    parser.add_argument("--effort", default="low", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--out", default="out")
    args = parser.parse_args(argv)

    try:
        out, items = run_shortlist([Path(p) for p in args.paths], provider=args.provider, model=args.model,
                                   effort=args.effort, out_base=Path(args.out))
    except (OSError, ValueError, AnalysisError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    failed = sum(s.reason.startswith("Batch failed") for s in items)
    if failed:
        print(f"warning: {failed} tenders were in a batch that failed; they are listed under 'needs manual check'. "
              "Re-run later to classify them.", file=sys.stderr)
    counts = {c: sum(s.category == c for s in items)
              for c in ("sbu2_power", "manual_check", "other_product_line", "not_relevant")}
    print(f"{counts['sbu2_power']} for SBU-2, {counts['manual_check']} to check by hand, "
          f"{counts['other_product_line']} for other teams, {counts['not_relevant']} not relevant")
    for name in ("digest.html", "shortlist.xlsx", "shortlist.json"):
        print(out / name)
    return 0


def run_shortlist(paths: list[Path], *, provider: str = "claude", model: str | None = None, effort: str = "low",
                  out_base: Path = Path("out"), out_dir: Path | None = None) -> tuple[Path, list]:
    """Screen the exports and write digest.html, shortlist.xlsx and shortlist.json; returns (folder, items)."""
    today = date.today()
    tenders = read_tender_lists(paths)
    print(f"Screening {len(tenders)} tenders with {provider}...", file=sys.stderr)
    items = classify(tenders, provider=provider, model=model, effort=effort, today=today)

    out = out_dir or Path(out_base) / f"shortlist_{today:%Y-%m-%d}"
    if out_dir is None and out.exists():
        # Never overwrite an earlier run: its tracker may already hold Mahadevan's decisions.
        out = out.with_name(f"{out.name}_{datetime.now():%H%M%S}")
        n = 2
        while out.exists():
            out = out.with_name(f"{out.name}_{n}")
            n += 1
    try:
        out.mkdir(parents=True, exist_ok=out_dir is not None)
        (out / "digest.html").write_text(render_digest(items, today), encoding="utf-8")
        build_tracker(items).save(out / "shortlist.xlsx")
        data = [{**asdict(s.tender), "category": s.category, "route_to": s.route_to, "confidence": s.confidence,
                 "reason": s.reason, "days_left": s.days_left} for s in items]
        (out / "shortlist.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        raise OSError(f"could not write outputs ({exc}); close shortlist.xlsx if it is open and re-run") from exc
    return out, items


if __name__ == "__main__":
    sys.exit(main())
