# Mail Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans.

**Spec:** `docs/superpowers/specs/2026-10-29-mail-intake-design.md`

## Global Constraints
- All logic lives in Python (tested in Docker); `mailwatch.ps1` only moves data between Outlook and the API.
- Never call Outlook `Send()`; only `Save()` drafts.
- The same-origin and Host checks stay as they are. The watcher sends no Origin header and connects to `localhost:8010`.

## Review Focus
1. The same mail posted twice → one bid (`test_repeat_entry_id_is_idempotent`).
2. A BidAssist mail with both sheets → only Power supply is screened (`test_bidassist_mail_screens_only_configured_alert`).
3. Go when the pack generation fails → no reply is due, and the failure shows on the page (`test_go_reply_waits_for_pack`).
4. The decision changes after drafting → a new reply is due (`test_changed_decision_redue_reply`).
5. Reply text is HTML-escaped (`test_reply_html_escaped`).

### Task 1: Reply composer (`bidtriage/reply.py`, `tests/test_reply.py`)
`build_reply(assessment, decision, *, pack_placeholders: int | None, signature) -> dict(html, text)`

### Task 2: Intake and settings (`bidtriage/intake.py`, `prompts/intake.toml`)
`load_intake_settings()`, `classify_mail(bid) -> ("bidassist", [alert attachments to screen], [ignored]) | ("bid", ...)`

### Task 3: Web API and UI (`webapp.py`, templates, `tests/test_webapp.py`)
Routes: `POST /api/intake`, `GET /api/replies`, `POST /api/replies/<bid_id>/drafted`. Go auto-starts the draft job.
Meta, reply state and overview items.

### Task 4: Watcher (`mailwatch.ps1`) and live check
`-Once` for a single pass; `-IntervalSeconds 120` by default. Live run on the user's "Bid desk" folder.
