# BidAssist Shortlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** `shortlist.py <xlsx...>` turns BidAssist alert exports into a triaged digest and tracker sheet.
**Architecture:** A deterministic parser, batched structured classification (reusing call_claude/call_gemini), and deterministic HTML/XLSX output.
**Spec:** `docs/superpowers/specs/2026-10-27-bidassist-shortlist-design.md`

## Global Constraints
- Run in Docker: `docker compose run --rm bid ...`.
- No row is ever dropped: unclassified → "needs manual check".
- HTML is escaped and self-contained; same visual style as card.html.

## Review Focus
1. A sheet without the header row, or with extra blank/title rows above it → found or reported (`test_header_found_below_title_rows`, `test_missing_header_raises`).
2. The same tender in both sheets or both files → one row, flagged as a corrigendum (`test_dedupe_marks_corrigendum`).
3. The model omits or invents tender ids → omitted ones become manual check, invented ones are ignored (`test_missing_and_unknown_ids`).
4. Dates like "16-Oct-2026" or blank → days left computed or blank (`test_days_left_and_closed`).
5. Many rows → batched (`test_rows_are_batched`).

### Task 1: BidAssist parser (`bidtriage/bidassist.py`, `tests/test_bidassist.py`)
**Produces:**
- `@dataclass Tender(tender_id, tender_no, authority, amount, opening_date, closing_date, emd, location, summary, description, keyword, corrigendum: bool, source: str)`
- `read_tender_lists(paths: list[Path]) -> list[Tender]`
- `parse_date(text) -> date | None`
- [ ] Tests: `test_reads_both_sheets`, `test_header_found_below_title_rows`, `test_missing_header_raises`, `test_dedupe_marks_corrigendum`, `test_parse_date`. Watch them fail; implement; pass; commit.

### Task 2: Classifier (`bidtriage/shortlister.py`, `prompts/shortlist_system.md`, `tests/test_shortlister.py`)
**Produces:**
- `RowVerdict(tender_id, category: Literal["sbu2_power","other_product_line","not_relevant"], route_to, confidence: Literal["high","medium","low"], reason)`
- `Verdicts(verdicts: list[RowVerdict])`
- `@dataclass Shortlisted(tender: Tender, category: str, route_to: str, confidence: str, reason: str, days_left: int | None)`. Category `manual_check` is used when no verdict came back.
- `classify(tenders, *, provider, model, effort, today, client=None, batch_size=60) -> list[Shortlisted]`
- [ ] Tests: `test_rows_are_batched`, `test_missing_and_unknown_ids`, `test_days_left_and_closed`, `test_batch_text_lists_rows_and_profile`. Watch them fail; implement; pass; commit.

### Task 3: Outputs and CLI (`bidtriage/shortlist_out.py`, `shortlist.py`, `tests/test_shortlist_out.py`)
**Produces:**
- `render_digest(items, today) -> str`
- `build_tracker(items) -> Workbook`
- `shortlist.py main(argv) -> int` (args: `paths+`, `--provider`, `--model`, `--effort` default low, `--out` default `out`)
- [ ] Tests: `test_digest_sections_and_sorting`, `test_digest_escapes`, `test_tracker_has_decision_dropdown`, `test_cli_writes_outputs`, `test_cli_bad_file_errors`. Watch them fail; implement; pass; commit.
- [ ] Live run on both sample files with Gemini; check against the spec's success check.
