# Bid triage and response drafting

Three tools for the Rug-Rel SBU-2 bid process:

0. **`shortlist.py`** screens BidAssist alert exports and separates the few real power supply tenders from the keyword noise.

1. **`triage.py`** turns one bid email and its documents (RFQ PDFs, compliance and price sheets) into a one-page assessment card, so Mahadevan can decide Go / No-go / Ask in minutes.
2. **`draft.py`** turns an approved bid into editable response documents (technical compliance, buyer's compliance form, price sheet, declarations, pre-bid queries, checklist). Everything a person must decide or supply is a highlighted `[[placeholder]]`.

## Setup (Docker)

Windows Smart App Control on this PC blocks Python's compiled packages, so the tools run in a Linux container. Start Docker Desktop, then from the project folder:

```powershell
docker compose build
```

Credentials: set `$env:ANTHROPIC_API_KEY = "..."` for Claude, or `$env:GEMINI_API_KEY = "..."` for Gemini, in the same PowerShell window. Compose passes them into the container.

**Gemini (proof-of-concept only):** add `--provider gemini` (default model `gemini-3.8-flash`). Free-tier keys from aistudio.google.com work, but Google may use free-tier requests to improve its products, so the production setup is Claude on paid billing. The free tier often returns 503 "high demand"; retry, or try `--model gemini-3.6-flash`.

## Web app (buttons)

```powershell
$env:GEMINI_API_KEY = "..."      # or $env:ANTHROPIC_API_KEY
docker compose up -d web          # start; then open http://localhost:8010
docker compose down               # stop
```

- **Screen**: upload BidAssist "Tender List" .xlsx files. Candidates get **Go / No-go / Ask** buttons; decisions are saved into the tracker.
- **Run triage**: upload the bid email (.msg) or the RFQ PDFs plus the email text. The card appears on the bid page.
- **Generate response**: on the bid page. Then download each file, or **Download all (.zip)**.

Long steps run in the background; the page shows "Working…" and refreshes itself. Everything is stored under `data/` (git-ignored). The app is reachable from this PC only (port 8010, because 8000 is used by another local app).

### Straight from Outlook (mail watcher)

```powershell
powershell -ExecutionPolicy Bypass -File .\mailwatch.ps1        # keep running; Ctrl+C to stop
```

- Put BD's bid mails and BidAssist alert mails into the Outlook folder **Inbox › Bid desk** (drag them, or add an Outlook rule). The watcher picks each one up once and tags it "Bid desk: picked up".
- A bid mail becomes a bid and is triaged. A BidAssist alert is screened, but only its **Power supply** list (`prompts/intake.toml` › `screen_alerts`); "My Preference" is ignored for now.
- After Mahadevan's Go / No-go / Ask on the card, the reply to BD is created as a **ReplyAll draft in your Outlook Drafts**, with Mahadevan in CC and the response pack attached on Go. It is never sent automatically.
- Needs classic Outlook open and the web app running.
- If you add an Outlook rule, make it match only new mails from BD or BidAssist (not "RE:" replies, and not mail from yourself), otherwise replies in the thread would each become a new bid and a new AI run.
- Tests for the watcher's own logic: `powershell -ExecutionPolicy Bypass -File .\tests\test_mailwatch.ps1`.

The same steps are also available as commands:

## 0. Screen the BidAssist alerts

Save the Excel files attached to the BidAssist alert emails (`<alert>-Tender List_<date>.xlsx`) and run:

```powershell
docker compose run --rm bid shortlist.py "samples/Power supply-Tender List_26092026.xlsx" "samples/My Preference-Tender List_26092026.xlsx" --provider gemini
```

Output in `out/shortlist_<date>/`:
- `digest.html`: SBU-2 candidates first (soonest deadline first, with the reason), then rows to check by hand, tenders for other teams, and the not-relevant ones with reasons
- `shortlist.xlsx`: every tender with its verdict, plus a **Decision** dropdown (Go / No-go / Ask) and Notes column for Mahadevan
- `shortlist.json`: structured data

No tender is ever dropped: anything the model doesn't classify is listed under "needs manual check".

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
