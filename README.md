# Bid triage and response drafting

Two tools for the Rug-Rel SBU-2 bid process:

1. **`triage.py`** turns one bid email and its documents (RFQ PDFs, compliance and price sheets) into a one-page assessment card, so Mahadevan can decide Go / No-go / Ask in minutes.
2. **`draft.py`** turns an approved bid into editable response documents (technical compliance, buyer's compliance form, price sheet, declarations, pre-bid queries, checklist). Everything a person must decide or supply is a highlighted `[[placeholder]]`.

## Setup (Docker)

Windows Smart App Control on this PC blocks Python's compiled packages, so the tools run in a Linux container. Start Docker Desktop, then from the project folder:

```powershell
docker compose build
```

Credentials: set `$env:ANTHROPIC_API_KEY = "..."` for Claude, or `$env:GEMINI_API_KEY = "..."` for Gemini, in the same PowerShell window. Compose passes them into the container.

**Gemini (proof-of-concept only):** add `--provider gemini` (default model `gemini-3.8-flash`). Free-tier keys from aistudio.google.com work, but Google may use free-tier requests to improve its products, so the production setup is Claude on paid billing. The free tier often returns 503 "high demand"; retry, or try `--model gemini-3.6-flash`.

## 1. Triage a bid

```powershell
docker compose run --rm bid triage.py samples/ahru-hal-hyd --provider gemini
```

The input is a folder holding the attachments plus an optional `email.txt` (headers such as `Subject:` and `From:`, a blank line, then the body), or an Outlook `.msg` / `.eml` file.

Output in `out/<date>_<rfq-number>/`:
- `card.html`: the card; open it in a browser or paste it into an email
- `card.md`: the same card as Markdown
- `assessment.json`: structured data

## 2. Draft the response (after "Go")

```powershell
docker compose run --rm bid draft.py samples/ahru-hal-hyd --card out/2026-10-21_hal-hyd-imm-indg-m1-psm-ahru-2026-01 --provider gemini
```

Output in `out/<bid>/response/`:

| File | What to do with it |
|---|---|
| `Technical_Compliance.docx` | Mahadevan: resolve every yellow `[[REVIEW]]` / `[[DEVIATION]]` |
| `Compliance_Statement.docx` | Buyer's compliance form; check Y/N and fill placeholders |
| `Price_Bid.xlsx` | BD: enter unit prices and GST % in yellow cells; totals calculate |
| `Declarations.docx` | MLC, land-border and MSE declarations; print on letterhead and sign |
| `PreBid_Queries.docx` | Clarification letter to the buyer, from the contradictions found |
| `Checklist.md` | Every document the RFQ requires |

The tool never writes prices, and never claims a certification or registration that `prompts/company_profile.toml` doesn't record.

## Tuning

- `prompts/company_profile.toml`: company facts (GSTIN, Udyam, signatory, certifications). **Fill this in once**; every draft uses it.
- `prompts/capability_profile.md`: what SBU-2 builds. Mahadevan should complete the `[CONFIRM]` items.
- `prompts/system.md`: what triage looks for. `prompts/draft_system.md`: how responses are drafted.

`samples/` and `out/` are git-ignored because they contain customer tender documents.

## Tests

```powershell
docker compose run --rm bid -m pytest
```
