# Bid Triage Prototype — Design

**Date:** 2026-10-21
**Status:** Approved in chat, awaiting spec review

## Problem

BD forwards many bid emails (GeM via Bid Assist, plus direct RFQs such as HAL manual
tenders) to Mahadevan, who must judge feasibility for each. He also heads the power
supply team, so bids get missed and business is lost. Each feasibility check means
reading a long RFQ pack (e.g. the 39-page HAL AHRU PSM RFQ).

## Goal of this prototype

Prove that Claude can turn one bid email + attachments into a one-page assessment card
accurate enough that Mahadevan can make a Go / No-go / Ask decision from the card alone.
The tuned prompt and output schema carry over to the production n8n pipeline later.

## Success criteria

1. For the HAL AHRU RFQ, the card surfaces at least: 100 ms hold-up as a key design
   risk; the "3 VPEL" overload rail absent from the output list; MIL-STD-461C vs 461E
   inconsistency; IPR/source-code handover to HAL; payment only after development
   completion/certification; 15-year obsolescence support with redesign at vendor cost;
   manual tender-box submission (not GeM); ≥50% local content.
2. Every factual item cites its source (document + page where available).
3. Mahadevan reviews cards for 5–10 real bids and judges them correct and complete.

## Scope

**In:** local CLI; `.msg`, `.eml`, or folder input; PDF and Excel attachments; one
Claude call per bid; Markdown, HTML and JSON outputs.

**Out (later, in n8n):** mailbox polling, Teams/email approval buttons, decision
tracker, deadline reminders, technical-document drafting.

## Approach

Single Claude API call per bid (`claude-opus-5-5`, adaptive thinking, effort `high`),
with PDFs sent as native document blocks so tables and scanned pages are read
correctly. Response constrained to a Pydantic `BidAssessment` schema via structured
outputs. Server-side refusal fallback enabled.

Rejected alternatives: two-stage per-document summarisation (only needed for packs
over request limits); local text extraction (loses table structure).

## Components

| Unit | Responsibility | Depends on |
|---|---|---|
| `triage.py` | CLI: parse args, run pipeline, print output paths | all below |
| `bidtriage/email_loader.py` | `.msg` / `.eml` / folder → `Bid` (subject, sender, date, body, attachments as name + bytes) | `extract-msg`, stdlib `email` |
| `bidtriage/attachments.py` | Attachment → Claude content block. PDF → base64 document block; xlsx/xls/csv → text table; other types → recorded as skipped | `openpyxl` |
| `bidtriage/analyzer.py` | Builds request (system prompt + capability profile + bid), calls Claude, returns `BidAssessment` | `anthropic`, `pydantic` |
| `bidtriage/schema.py` | `BidAssessment` Pydantic model | `pydantic` |
| `bidtriage/render.py` | `BidAssessment` + skipped files → Markdown and HTML card | stdlib |
| `prompts/system.md` | Analysis instructions | — |
| `prompts/capability_profile.md` | Rug-Rel SBU-2 product lines, input/output/cooling ranges, standards, past work, accepted terms, and the SBU-2 MIR question checklist. Seeded from the SBU-2 BD deck and the ATRU compliance submission; `[CONFIRM]` items await Mahadevan | — |

## BidAssessment schema (fields)

- `customer`, `division`, `rfq_number`, `title`, `issue_date`, `due_date`,
  `submission_mode` (GeM / manual / e-procurement / other), `bid_contact`
- `summary` — two or three sentences on what is being bought
- `key_specs` — list of {parameter, value, source}
- `quantities` — list of {phase, item, qty, firm_or_anticipated, source}
- `technical_risks` — list of {risk, why_it_matters, severity, source}
- `contradictions` — list of {issue, source}
- `commercial_red_flags` — list of {term, implication, source}
- `eligibility` — list of {requirement, source}
- `timeline` — list of {milestone, when, source}
- `fit_verdict` — strong / possible / poor / unclear
- `fit_reasons` — list of strings referencing the capability profile
- `questions_for_reviewer` — list of strings; for missing information, phrased
  along the SBU-2 MIR checklist (input, rails, power, cooling, form factor,
  application, temperature, project status, quantities, budget, competitors)
- `documents_read` — list of filenames the model actually used

## Data flow

```
input path → email_loader → Bid → attachments → content blocks
          → analyzer (Claude) → BidAssessment → render → out/<date>_<rfq-slug>/
                                                          card.md, card.html, assessment.json
```

## Error handling

- Request over 32 MB or 600 PDF pages → abort with a clear message; never truncate.
- `stop_reason == "refusal"` (after fallback) or `max_tokens` → abort, no partial card.
- API errors: SDK retries transient failures; others surface with the error message.
- Unsupported attachment types listed under "Not read" on the card.

## Testing

- Unit: email loading from a synthetic `.eml` with PDF + xlsx attachments; folder mode;
  attachment conversion; rendering from a fixture `BidAssessment`.
- Live (manual, costs money): AHRU RFQ folder, checked against success criterion 1.

## Future phase (not in this prototype)

Draft the technical compliance document for approved bids. Mahadevan's existing
format (see the ATRU submission) is a clause-by-clause table: every RFQ clause with
a "Rug-Rel Compliance" column ("OK Complied", or a remark/deviation highlighted in
red). The `assessment.json` from this prototype is the starting point for that.

## Configuration

- `ANTHROPIC_API_KEY` from environment (or `ant auth login` profile).
- Model and effort overridable via CLI flags, defaulting to `claude-opus-5-5` / `high`.
- Provider is swappable later (e.g. `AnthropicFoundry` for Azure) inside `analyzer.py` only.
