# Local Web App: Design

**Date:** 2026-10-27
**Status:** Approved in chat ("yes build the web app")

## Goal

Buttons instead of commands. In a browser on this PC, a user can:
- screen BidAssist exports and record Go / No-go / Ask
- upload a bid (email + documents) and run triage
- view the card
- generate the response pack
- download each file, or all of them as a zip

## Shape

- Flask app (`webapp.py`, `bidtriage/web/`), served by Docker Compose service `web` at
  `http://localhost:8000`, bound to 127.0.0.1 only.
- **Same engine:** the CLIs' work is moved into `run_triage`, `run_draft` and `run_shortlist`, which the
  CLIs and the web app both call. No pipeline logic lives in the web layer.
- **Long AI steps run in a background thread.** The page shows "working…" and refreshes itself every 5 s
  (meta refresh, no JavaScript framework). Job state is stored in `status.json` next to the data, so it
  survives a restart.
- **Data folder `data/` (git-ignored):**
  - `data/bids/<id>/input/`: uploaded files and `email.txt`
  - `card/`: card.html, card.md, assessment.json
  - `card/response/`: the response pack and summary.json
  - `data/shortlists/<id>/`: the uploaded exports, digest, shortlist.xlsx and decisions.json
- **Bid input:** upload files (.msg/.eml, or PDFs/xlsx with subject and body typed into the form), or pick
  an existing folder from `samples/` for demos.
- **Provider:** a dropdown (Claude / Gemini). It defaults to Gemini when only `GEMINI_API_KEY` is set.

## Pages

- `/`: upload forms and lists of recent shortlists and bids, each with its status
- `/shortlists/<id>`: SBU-2 candidates with Go / No-go / Ask buttons; the chosen decision is highlighted,
  stored in `decisions.json` and written into `shortlist.xlsx`. Other teams and not-relevant tenders are collapsed.
  Download buttons for the digest and the xlsx.
- `/bids/<id>`: status, the card (embedded), a **Generate response** button, then the response files with
  placeholder counts, a download button each, and **Download all (.zip)**.

## Safety

Jinja autoescaping. Uploaded names are passed through `secure_filename`. Downloads are served only from
inside the bid or shortlist folder, so path traversal returns 404. Uploads are capped at 50 MB. Ids are generated.
Errors from a job are shown on the page.

## Out of scope

Multi-user access and logins, mailbox integration, editing documents in the browser.
