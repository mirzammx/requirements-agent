# Response Pack Drafting: Design

**Date:** 2026-10-26
**Status:** Design approved in chat ("build it")
**Builds on:** `2026-10-21-bid-triage-prototype-design.md`

## Goal

When Mahadevan decides "Go" on a bid, draft the documents BD and Mahadevan must submit, as editable
files. The draft is complete except where a human decision or a fact is needed. Those spots are
highlighted `[[...]]` placeholders, so the remaining work is filling in, not writing from scratch.

## Inputs

- The bid (folder / .msg / .eml), loaded and converted exactly as the triage tool does.
- The triage output `out/<bid>/assessment.json` (risks, contradictions, red flags).
- `prompts/company_profile.toml`: Rug-Rel facts (name, address, GSTIN, Udyam, signatory, certifications).
  An empty value means "unknown" and is never asserted.

## Outputs: `out/<bid>/response/`

| File | Modelled on | Content |
|---|---|---|
| `Technical_Compliance.docx` | Rug-Rel ATRU design compliance | Company header/footer; RFQ clauses grouped by RFQ section; table Sl. No / Description / Rug-Rel Compliance |
| `Compliance_Statement.docx` | HAL compliance statement form | Buyer's rows with Y/N response; bidder details from profile. Only when the RFQ has such a form |
| `Price_Bid.xlsx` | HAL price bid | Buyer's price lines and quantities; price cells blank and yellow; totals, GST and grand total as formulas |
| `Declarations.docx` | RFQ Appendix B, GFR 144(xi), MSE clauses | MLC self-certification, land-border declaration, MSE declaration, as the RFQ requires |
| `PreBid_Queries.docx` | Triage contradictions | Clarification letter to the buyer contact, one numbered query per issue |
| `Checklist.md` | RFQ submission rules | Every document/envelope required, marked drafted / to prepare |

Each .docx starts with a line counting its placeholders.

## Rules (enforced in code where possible)

1. **No prices.** The draft schema has no price field; price cells are always empty.
2. **No unbacked claims.** A clause marked "complied" that mentions AS9100, ISO 9001, CEMILAC, Udyam/MSE
   or HAL vendor registration is downgraded to a `[[CONFIRM: ...]]` placeholder when the matching
   profile field is empty.
3. **Review means a placeholder.** Any clause with status review/deviation gets `[[...]]` text, wrapped
   in code if the model omitted the brackets.
4. Clauses tied to triage risks, contradictions or red flags are review, not complied (prompt rule).

## Approach

One structured LLM call (Claude or Gemini, same `--provider` switch) returns a `ResponseDraft`.
Deterministic Python (python-docx, openpyxl) renders the files, so layout never depends on the model.
The provider code from the triage tool is generalised to take any schema and system prompt.

## Command

`python draft.py <bid> --card out/<bid-dir> [--provider gemini]`, run in Docker:
`docker compose run --rm bid draft.py samples/ahru-hal-hyd --card out/<dir> --provider gemini`.

## Out of scope

GeM ingestion; editing buyer-supplied Word/Excel files in place; submission.

## Success check (AHRU)

The technical compliance covers Part-B/C/D and Annexure-1. The hold-up and EMI clauses are review.
The price sheet has HAL's 8 lines with blank prices. The compliance statement has HAL's 6 rows. The
pre-bid letter lists the card's contradictions. No AS9100/CEMILAC compliance is claimed while the
profile is empty.
