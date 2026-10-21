# Bid triage prototype

Turns one bid email and its documents (RFQ PDFs, compliance and price sheets) into a one-page assessment card, so the power supply team can decide Go / No-go / Ask in minutes instead of reading the whole tender.

## Setup

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Windows; use .venv/bin/pip on Linux/macOS
```

Credentials: set `ANTHROPIC_API_KEY`, or run `ant auth login` once.

## Usage

```bash
.venv/Scripts/python triage.py samples/ahru-hal-hyd       # a folder
.venv/Scripts/python triage.py "path/to/bid email.msg"   # an email saved from Outlook (drag it to a folder)
```

A folder input holds the attachments plus an optional `email.txt` (headers such as `Subject:` and `From:`, then a blank line, then the body).

Options: `--model` (default `claude-opus-5-5`), `--effort` (`low` to `max`, default `high`), `--out` (default `out`).

## Output

`out/<date>_<rfq-number>/`:

- `card.md`: the card
- `card.html`: the same card, ready to paste into an email
- `assessment.json`: structured data for the later n8n pipeline and the tracker

Attachments that could not be read (Word files, images, forwarded emails, corrupt spreadsheets) are listed under "Not read" on the card.

## Tuning

- `prompts/system.md`: what the analyst looks for
- `prompts/capability_profile.md`: what Rug-Rel SBU-2 builds. Mahadevan should complete the `[CONFIRM]` items.

`samples/` and `out/` are git-ignored because they contain customer tender documents.

## Tests

```bash
.venv/Scripts/python -m pytest
```
