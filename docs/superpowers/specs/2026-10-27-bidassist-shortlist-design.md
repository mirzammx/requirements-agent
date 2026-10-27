# BidAssist Shortlist: Design

**Date:** 2026-10-27
**Status:** Design approved in chat ("yes do it")

## Problem

BidAssist keyword alerts (e.g. "power supply") match many irrelevant tenders: civil electrical works,
DG sets, seal kits. In the 26-Sep "Power supply" export, 2 of 6 tenders were relevant. BD forwards
the noise, and Mahadevan misses the real ones.

## Input

One or more BidAssist alert exports (`<alert>-Tender List_<ddmmyyyy>.xlsx`), each with sheets
"Tender List_<date>" (new) and "Tender Updated_<date>" (corrigenda). The header row has
Tender Id, Tender No, Tender Authority, Tender Amount, Opening Date, Closing Date, EMD, Document Cost,
Tender Fee, Location, Summary, Description, Matching Keyword, Corrigendum (Y/N).

## Output: `out/shortlist_<date>/`

- `digest.html`: for Mahadevan. Sections: **SBU-2 power supply candidates** (sorted by closing date,
  with days left and a reason), **Needs manual check** (rows the model did not classify),
  **Other product lines** (grouped by suggested team), **Not relevant** (collapsed, with a reason each).
- `shortlist.xlsx`: every row with category, route, confidence, reason and days left, plus empty
  **Decision** (dropdown Go / No-go / Ask) and **Notes** columns. This seeds the decision tracker.
- `shortlist.json`: structured data.

## Approach

1. Parse the rows deterministically (openpyxl) and dedupe by Tender Id; a row in "Tender Updated" is a corrigendum.
2. Classify in batches (60 rows per call) with one structured model call per batch, judged against the
   capability profile: `sbu2_power` / `other_product_line` (with suggested team) / `not_relevant`,
   plus confidence and a one-line reason. The same `--provider` switch as the other tools; effort low.
3. Fail safe: any row without a verdict is "needs manual check" and is never dropped. Rows past their
   closing date are marked closed but still shown.

## Out of scope (next steps)

Downloading GeM bid documents (needs a feasibility check first); reading the BidAssist email itself
(the .xlsx is the input for now); mailbox automation (n8n).

## Success check

On `samples/Power supply-Tender List_26092026.xlsx`: BEL Variable SMPS and DRDO AC-DC power supplies
are `sbu2_power`; the MES works, the DG set, the ISRO electrical works and the DRDO seal kit are `not_relevant`.
On "My Preference": servers, firewalls, joysticks, Ethernet switches and Kavach are routed as other product lines.
