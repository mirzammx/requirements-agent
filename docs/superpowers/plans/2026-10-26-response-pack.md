# Response Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]` checkboxes.

**Goal:** `draft.py` turns a bid and its triage assessment into editable response files with highlighted placeholders.
**Architecture:** One structured LLM call returns a `ResponseDraft`. Code guards enforce no prices and no unbacked claims, and deterministic builders write the .docx/.xlsx/.md files.
**Tech Stack:** Python 3.11 in Docker (`compose.yaml`), python-docx, openpyxl, tomllib, existing provider modules.
**Spec:** `docs/superpowers/specs/2026-10-26-response-pack-design.md`

## Global Constraints
- Run everything with `docker compose run --rm bid ...`. The Windows venv is blocked by Smart App Control.
- Placeholder syntax `[[...]]`, rendered bold on yellow highlight in .docx and yellow fill in .xlsx.
- No price values anywhere; `ResponseDraft` has no price field.
- An empty `company_profile.toml` value is never asserted.
- Existing triage behaviour and its tests stay unchanged.

## Review Focus
1. RFQ without a buyer compliance form → no Compliance_Statement.docx (`test_no_form_rows_returns_none`).
2. Model marks a review clause without brackets → wrapped (`test_review_without_placeholder_is_wrapped`).
3. Complied AS9100/CEMILAC clause with an empty profile field → downgraded (`test_unbacked_certification_claim_downgraded`).
4. Price line quantity like "10 Nos" or "not stated" → the formula still works or is left blank (`test_non_numeric_qty_leaves_formula_cells_blank`).
5. Company profile file missing or with a missing key → every field is treated as unknown (`test_missing_profile_fields_are_unknown`).

---

### Task 1: Generalise the provider calls
**Files:** modify `bidtriage/analyzer.py` and `bidtriage/gemini_analyzer.py`; test `tests/test_analyzer.py` and `tests/test_gemini_analyzer.py`.
**Produces:**
- `call_claude(system: str, blocks: list[dict], text: str, schema: type[BaseModel], *, client=None, model, effort) -> BaseModel`
- `call_gemini(system, blocks, text, schema, *, client=None, model, effort) -> BaseModel`
- `analyze` / `analyze_gemini` keep their signatures and delegate to these.
- [ ] Add `test_call_claude_validates_against_given_schema` and `test_call_gemini_validates_against_given_schema` (a tiny schema `class Tiny(BaseModel): x: str`). Watch them fail.
- [ ] Refactor. The whole suite stays green. Commit.

### Task 2: Company profile, draft schema and guards
**Files:** create `prompts/company_profile.toml`, `bidtriage/profile.py`, `bidtriage/draft_schema.py`, `bidtriage/guards.py`; test `tests/test_guards.py`.
**Produces:**
- `load_profile(path=None) -> dict[str, str]`, with defaults for every key in `PROFILE_KEYS` (missing → "").
- `ResponseDraft` with the fields below. Field descriptions carry instructions to the model.
  - `ClauseResponse(ref, requirement, status: Literal["complied","review","deviation","noted","not_applicable"], response, source)`
  - `ComplianceSection(heading, clauses)`
  - `FormRow(sno, term, response)`
  - `PriceLine(phase, sno, description, qty)`
  - `RequiredDocument(document, notes, source)`
  - `PreBidQuery(clause_ref, query, source)`
  - top-level fields: `rfq_number, title, buyer_name, buyer_address, buyer_contact, due_date, offer_validity_date, sections, compliance_form_title, compliance_form_rows, price_schedule_title, price_lines, required_documents, prebid_queries, declarations_needed: list[Literal["mlc","land_border","mse"]]`
- `apply_guards(draft, profile) -> ResponseDraft`: wraps review/deviation clauses whose response lacks `[[`, and downgrades unbacked certification claims.
- `CERT_FIELDS = {"AS9100": "as9100", "ISO 9001": "iso_9001", "CEMILAC": "cemilac_approvals", "Udyam": "udyam_number", "MSE": "udyam_number", "vendor registration": "buyer_vendor_codes"}`
- [ ] Tests: `test_missing_profile_fields_are_unknown`, `test_review_without_placeholder_is_wrapped`, `test_unbacked_certification_claim_downgraded`, `test_backed_certification_claim_kept`. Watch them fail; implement; pass; commit.

### Task 3: Word builders and checklist
**Files:** create `bidtriage/docx_out.py`; test `tests/test_docx_out.py`; fixture `tests/draft_fixtures.py::sample_draft()`.
**Produces:**
- `add_rich(paragraph, text)`: `[[...]]` spans become bold runs highlighted yellow.
- `count_placeholders(text) -> int`
- `build_technical_compliance(draft, profile) -> Document`
- `build_compliance_statement(draft, profile) -> Document | None`
- `build_declarations(draft, profile, today) -> Document`
- `build_prebid_queries(draft, profile, today) -> Document`
- `build_checklist(draft) -> str`
- An unknown profile value renders as `[[<label>]]`.
- [ ] Tests:
  - `test_placeholders_are_highlighted_runs`
  - `test_technical_compliance_has_section_tables_and_count`
  - `test_no_form_rows_returns_none`
  - `test_compliance_statement_uses_profile_or_placeholder`
  - `test_declarations_include_requested_kinds_only`
  - `test_prebid_letter_numbers_queries`
  - `test_checklist_lists_documents`

  Watch them fail; implement; pass; commit.

### Task 4: Price sheet
**Files:** create `bidtriage/xlsx_out.py`; test `tests/test_xlsx_out.py`.
**Produces:** `build_price_bid(draft) -> Workbook`
- Columns: S.No | Description | Qty | Unit Price excl. GST | Total excl. GST | GST % | Total incl. GST.
- Rows are grouped by phase, with a subtotal per phase and a grand total.
- Unit price and GST % cells are empty with yellow fill.
- Totals are formulas. A non-numeric qty leaves the qty cell as text and the formula cells empty.
- [ ] Tests:
  - `test_price_lines_and_quantities`
  - `test_price_cells_blank_and_highlighted`
  - `test_totals_are_formulas`
  - `test_non_numeric_qty_leaves_formula_cells_blank`

  Watch them fail; implement; pass; commit.

### Task 5: Drafter, prompt and CLI
**Files:** create `bidtriage/drafter.py`, `prompts/draft_system.md`, `draft.py`; test `tests/test_drafter.py`.
**Produces:**
- `draft_user_text(bid, blocks, skipped, assessment, profile, today) -> str`. Includes the assessment JSON and the profile.
- `draft_response(bid, blocks, skipped, assessment, *, provider, model, effort, today, client=None) -> ResponseDraft`. Runs `apply_guards`.
- `draft.py main(argv) -> int`
  - Args: `path`, `--card DIR` (required, must contain `assessment.json`), `--provider`, `--model`, `--effort`.
  - Writes `DIR/response/*`. Prints paths and placeholder counts.
  - Errors exit 1 with `error:`.
- [ ] Tests:
  - `test_user_text_contains_assessment_and_profile`
  - `test_draft_response_applies_guards` (fake provider)
  - `test_cli_writes_response_files`
  - `test_cli_missing_card_errors`

  Watch them fail; implement; pass; commit.
- [ ] Live run on AHRU with Gemini; check against the spec's success check; record the result.
