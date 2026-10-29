# Mail Intake and Reply Drafts: Design

**Date:** 2026-10-29
**Status:** Approved in chat

## Goal

Read bid mails straight from the user's Outlook, and draft the reply to BD after Mahadevan decides.
Nobody saves or uploads email, and nobody writes the reply from scratch. Nothing is ever sent automatically.

## Flow

1. The user's Outlook has a folder called **"Bid desk"**. The user drags mails in, or an Outlook rule files them there.
2. **Watcher** (`mailwatch.ps1`, PowerShell plus the running classic Outlook, polling every 2 min):
   - saves each new mail in the folder as `.msg` and posts it to `POST /api/intake` with its Outlook EntryID;
   - on success, tags the mail with the Outlook category "Bid desk: picked up".
   The watcher holds no business logic.
3. **Intake** (Python, tested) decides what the mail is:
   - **A BidAssist alert** has attachments matching `*Tender List*.xlsx`. Only the alerts listed in
     `prompts/intake.toml` `screen_alerts` (initially `["Power supply"]`) are screened, as one shortlist run.
     Other alerts (e.g. "My Preference") are ignored and logged. If no listed alert is attached, the mail
     is recorded as ignored.
   - **Anything else** is a bid mail. A bid is created from the `.msg` (the email plus its attachments) and triage runs.
   - Each EntryID is processed once. A repeat returns the earlier result.
4. Mahadevan decides **Go / No-go / Ask** on the card, as before.
   - **Go** automatically starts "Generate response" if no pack exists yet.
5. **Reply ready**:
   - No-go and Ask are ready immediately.
   - Go is ready once the pack exists and no job is running. The pack is then zipped to `response/<title>_response.zip`.
6. The watcher fetches `GET /api/replies`. For each ready reply it opens the original mail by EntryID, makes a
   **ReplyAll**, puts our text above the quoted thread, adds Mahadevan in CC, attaches the zip (Go only),
   **saves it to Drafts** and posts `POST /api/replies/<bid>/drafted`. If the decision changes later, a new draft
   becomes due.

## Reply text (built from the card by code; no AI call, nothing invented)

- **Go:** feasible; a two-or-three-sentence summary; key technical risks; the pre-bid queries / extension
  (when the deadline has passed or is close); the response pack attached, with its placeholder count.
- **No-go:** not pursuing; the reasons from the card's fit reasons and its high risks.
- **Ask:** need clarification; the questions from the card.
- All three end with "On behalf of Mahadevan, SBU-2". The HTML is escaped.

## App changes

- A bid created from mail stores `meta.mail` (entry_id, subject, sender, received) and shows "From your mail of …".
- The bid page shows the reply state: due / drafted (with time) / not applicable.
- The overview shows "You · send the reply from Outlook Drafts" for 3 days after drafting.

## Settings: `prompts/intake.toml`

`screen_alerts`, `mahadevan_email` (default `mahadevan.velvalli@rugrel.com`), `signature`.

## Out of scope

Running while Outlook is closed or the PC is off (that needs Graph or Power Automate on a server);
sending mail; reading folders other than "Bid desk".
