# Bid Triage Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A CLI, `python triage.py <bid>`, that turns one bid email and its attachments into a one-page assessment card (Markdown, HTML, JSON) using one Claude API call.

**Architecture:** Load the email into a `Bid`. Convert the attachments into Claude content blocks: PDFs as native document blocks, spreadsheets as text. Make one streaming `messages.stream(..., output_format=BidAssessment)` call. Render the parsed result to files under `out/`. Each stage is a separate module with a pure interface, so everything except the API call is unit-tested offline.

**Tech Stack:** Python 3.11, `anthropic` (latest), `pydantic` v2, `extract-msg`, `openpyxl`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-10-21-bid-triage-prototype-design.md`

## Global Constraints

- Model default `claude-opus-5-5`, effort default `high`; both overridable with `--model` / `--effort`.
- Adaptive thinking: omit the `thinking` param (Opus 5.5 always thinks). Never send `budget_tokens` or `{"type":"disabled"}`.
- Server-side refusal fallback on every call: header `anthropic-beta: server-side-fallback-2026-07-01`, body `fallbacks: "default"` (sent via `extra_headers` / `extra_body`).
- Streaming with `max_tokens=64000`; read the result via `stream.get_final_message().parsed_output`.
- Request size guard: abort if total base64 attachment payload exceeds 30 MB (API limit 32 MB). Never truncate inputs.
- `stop_reason` of `refusal` or `max_tokens` → raise `AnalysisError`; never write a partial card.
- Credentials come only from the environment (`ANTHROPIC_API_KEY` or an `ant auth login` profile). No keys in code or files.
- `out/` and `samples/` stay git-ignored (already in `.gitignore`).
- Provider-specific code lives only in `bidtriage/analyzer.py`.

## Review Focus

1. **The bid's due date has already passed** (e.g. AHRU's 13 Oct): the model must know today's date to say so. Pinned by `test_build_request_includes_today` (Task 4).
2. **Folder input with no `email.txt`**: should still analyse the attachments, with an empty body. Pinned by `test_load_folder_without_email_txt` (Task 1).
3. **Corrupt or password-protected spreadsheet**: should be listed as "not read" with the reason, not crash the run. Pinned by `test_corrupt_xlsx_is_skipped_with_reason` (Task 2).
4. **Word documents, images, or emails forwarded as attachments**: listed under "Not read" on the card. Pinned by `test_unsupported_types_are_skipped` (Task 2) and `test_card_lists_unread_files` (Task 3).
5. **RFQ numbers with slashes** (e.g. `HAL/HYD/IMM-INDG/M1/PSM-AHRU/2026/01`): must produce a safe folder name. Pinned by `test_output_dir_slug_is_filesystem_safe` (Task 5).

---

### Task 1: Project setup and email loader

**Files:**
- Create: `requirements.txt`, `bidtriage/__init__.py`, `bidtriage/models.py`, `bidtriage/email_loader.py`
- Test: `tests/test_email_loader.py`

**Interfaces:**
- Produces, in `bidtriage/models.py`:
  - `@dataclass Attachment(filename: str, data: bytes, content_type: str)`
  - `@dataclass Bid(subject: str, sender: str, date: str, body: str, attachments: list[Attachment], source_path: str)`
- Produces, in `bidtriage/email_loader.py`: `load_bid(path: str | Path) -> Bid`, dispatching on `.eml`, `.msg`, or a directory. Raises `ValueError` for anything else.

- [ ] **Step 1: Create `requirements.txt` and install**

```
anthropic
pydantic>=2
extract-msg
openpyxl
pytest
```

Run: `python -m venv .venv && .venv/Scripts/pip install -r requirements.txt`
Expected: installs without error.

- [ ] **Step 2: Write the failing tests**

```python
def test_load_eml_with_attachments(tmp_path):
    # Build an EmailMessage: subject "AHRU Power Supply Requirement- HAL HYDERABAD",
    # from "imran.khan@rugrel.com", plain body "Check the feasibility.",
    # attachments rfq.pdf (b"%PDF-1.4 fake", application/pdf) and qty.xlsx (bytes, xlsx mime).
    bid = load_bid(eml_path)
    assert bid.subject == "AHRU Power Supply Requirement- HAL HYDERABAD"
    assert "imran.khan@rugrel.com" in bid.sender
    assert "Check the feasibility." in bid.body
    assert [a.filename for a in bid.attachments] == ["rfq.pdf", "qty.xlsx"]
    assert bid.attachments[0].data == b"%PDF-1.4 fake"

def test_load_folder_reads_email_txt_and_files(tmp_path):
    # tmp_path/email.txt contains "Subject: Test bid\n\nBody line"; plus a.pdf and b.csv
    bid = load_bid(tmp_path)
    assert bid.subject == "Test bid"
    assert "Body line" in bid.body
    assert sorted(a.filename for a in bid.attachments) == ["a.pdf", "b.csv"]

def test_load_folder_without_email_txt(tmp_path):
    # only a.pdf present
    bid = load_bid(tmp_path)
    assert bid.body == ""
    assert bid.subject == tmp_path.name
    assert [a.filename for a in bid.attachments] == ["a.pdf"]

def test_unknown_path_type_raises(tmp_path):
    p = tmp_path / "bid.docx"; p.write_bytes(b"x")
    with pytest.raises(ValueError):
        load_bid(p)
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_email_loader.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 4: Implement `load_bid` in `bidtriage/email_loader.py`**

How each input type is read:
- `.eml`: stdlib `email.message_from_bytes(..., policy=email.policy.default)`. Body is `get_body(preferencelist=("plain","html"))`; attachments come from `iter_attachments()`.
- `.msg`: `extract_msg.Message(path)`. Map `.subject`, `.sender`, `.date`, `.body`; each `.attachments` item gives `.longFilename or .shortFilename` and `.data`. An attachment whose `.data` is not `bytes` (an embedded message) becomes `Attachment(filename=<name>.msg, data=b"", content_type="message/rfc822")`, so it shows up as unread later.
- Folder:
  - If `email.txt` exists, parse its leading `Header: value` lines up to the first blank line (`Subject` and `From` are used); the rest is the body. The BD sample uses `From:`/`Sent:`/`Subject:` lines.
  - If there is no `Subject` header, the subject is the folder name.
  - Every other file in the folder (not recursive) is an attachment, with `content_type` from `mimetypes.guess_type`.

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `.venv/Scripts/python -m pytest tests/test_email_loader.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt bidtriage tests
git commit -m "feat: load bids from .eml, .msg and folders"
```

---

### Task 2: Attachments to Claude content blocks

**Files:**
- Create: `bidtriage/attachments.py`
- Test: `tests/test_attachments.py`

**Interfaces:**
- Consumes: `Attachment` (Task 1).
- Produces:
  - `@dataclass Skipped(filename: str, reason: str)`
  - `to_content_blocks(attachments: list[Attachment]) -> tuple[list[dict], list[Skipped]]`
  - `MAX_PAYLOAD_BYTES = 30 * 1024 * 1024`
  - `class PayloadTooLarge(Exception)`, raised by `to_content_blocks` when the summed base64 length exceeds `MAX_PAYLOAD_BYTES`. The message names each file and its size in MB.

- [ ] **Step 1: Write the failing tests**

```python
def test_pdf_becomes_document_block():
    blocks, skipped = to_content_blocks([Attachment("rfq.pdf", b"%PDF-1.4", "application/pdf")])
    assert blocks[0]["type"] == "document"
    assert blocks[0]["source"] == {"type": "base64", "media_type": "application/pdf",
                                   "data": base64.b64encode(b"%PDF-1.4").decode()}
    assert blocks[0]["title"] == "rfq.pdf"
    assert skipped == []

def test_xlsx_becomes_text_table(tmp_path):
    # openpyxl workbook, sheet "Price", rows ["Item","Qty"], ["PSM",4]
    blocks, _ = to_content_blocks([Attachment("price.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")])
    assert blocks[0]["type"] == "text"
    assert "=== price.xlsx / sheet Price ===" in blocks[0]["text"]
    assert "PSM\t4" in blocks[0]["text"]

def test_csv_and_txt_become_text():
    blocks, _ = to_content_blocks([Attachment("q.csv", b"a,b\n1,2", "text/csv")])
    assert "=== q.csv ===" in blocks[0]["text"] and "1,2" in blocks[0]["text"]

def test_unsupported_types_are_skipped():
    _, skipped = to_content_blocks([Attachment("spec.docx", b"x", ""), Attachment("fwd.msg", b"", "message/rfc822"),
                                    Attachment("photo.jpg", b"x", "image/jpeg")])
    assert [s.filename for s in skipped] == ["spec.docx", "fwd.msg", "photo.jpg"]
    assert all(s.reason for s in skipped)

def test_corrupt_xlsx_is_skipped_with_reason():
    _, skipped = to_content_blocks([Attachment("bad.xlsx", b"not a zip", "")])
    assert skipped[0].filename == "bad.xlsx" and "could not read" in skipped[0].reason

def test_payload_over_limit_raises(monkeypatch):
    monkeypatch.setattr(attachments, "MAX_PAYLOAD_BYTES", 10)
    with pytest.raises(PayloadTooLarge, match="big.pdf"):
        to_content_blocks([Attachment("big.pdf", b"x" * 100, "application/pdf")])
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_attachments.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement `to_content_blocks` in `bidtriage/attachments.py`**

Decide by lowercase file extension:
- `.pdf` → document block.
- `.xlsx` / `.xlsm` → `openpyxl.load_workbook(BytesIO, read_only=True, data_only=True)`. One text section per sheet, cells tab-joined, `None` written as empty.
- `.csv` / `.txt` → text block, decoded as UTF-8 with `errors="replace"`.
- Everything else → `Skipped(name, "unsupported file type <ext>")`.
- Any exception while reading a spreadsheet → `Skipped(name, f"could not read: {exc}")`.

Keep the original attachment order.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `.venv/Scripts/python -m pytest tests/test_attachments.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add bidtriage/attachments.py tests/test_attachments.py
git commit -m "feat: convert attachments to Claude content blocks"
```

---

### Task 3: Assessment schema and card rendering

**Files:**
- Create: `bidtriage/schema.py`, `bidtriage/render.py`, `tests/fixtures.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Produces, in `bidtriage/schema.py`: the Pydantic `BidAssessment` model with exactly the spec's fields.
  - Nested models: `Spec(parameter, value, source)`, `Quantity(phase, item, qty, firm_or_anticipated: Literal["firm","anticipated","unclear"], source)`, `Risk(risk, why_it_matters, severity: Literal["high","medium","low"], source)`, `Contradiction(issue, source)`, `RedFlag(term, implication, source)`, `Requirement(requirement, source)`, `Milestone(milestone, when, source)`.
  - Top-level fields: `customer`, `division`, `rfq_number`, `title`, `issue_date`, `due_date`, `submission_mode: Literal["GeM","manual","e-procurement","other","unclear"]`, `bid_contact`, `summary`, `key_specs: list[Spec]`, `quantities: list[Quantity]`, `technical_risks: list[Risk]`, `contradictions: list[Contradiction]`, `commercial_red_flags: list[RedFlag]`, `eligibility: list[Requirement]`, `timeline: list[Milestone]`, `fit_verdict: Literal["strong","possible","poor","unclear"]`, `fit_reasons: list[str]`, `questions_for_reviewer: list[str]`, `documents_read: list[str]`.
  - Every string field is a plain `str`; the model writes `"not stated"` when information is missing. No `Optional` fields, which keeps the schema compatible with structured outputs.
- Produces, in `bidtriage/render.py`: `render_markdown(a: BidAssessment, skipped: list[Skipped], email_subject: str) -> str` and `render_html(...same args...) -> str`.
- Produces, in `tests/fixtures.py`: `sample_assessment() -> BidAssessment`, an AHRU-like instance used by Tasks 3 and 5.

- [ ] **Step 1: Write the failing tests**

```python
def test_markdown_card_sections_in_order():
    md = render_markdown(sample_assessment(), [], "AHRU Power Supply Requirement")
    order = ["Fit:", "Summary", "Key specs", "Quantities", "Technical risks", "Contradictions",
             "Commercial red flags", "Eligibility", "Timeline", "Questions for reviewer", "Documents"]
    positions = [md.index(h) for h in order]
    assert positions == sorted(positions)
    assert "HAL/HYD/IMM-INDG/M1/PSM-AHRU/2026/01" in md
    assert "RFQ_TenderDocument_PSMAHRU.pdf p.9" in md   # sources are shown

def test_card_lists_unread_files():
    md = render_markdown(sample_assessment(), [Skipped("spec.docx", "unsupported file type .docx")], "s")
    assert "Not read" in md and "spec.docx" in md and "unsupported file type .docx" in md

def test_html_escapes_content():
    a = sample_assessment(); a.summary = "<script>x</script>"
    html = render_html(a, [], "s")
    assert "<script>x</script>" not in html and "&lt;script&gt;" in html

def test_empty_lists_render_none_marker():
    a = sample_assessment(); a.contradictions = []
    assert "Contradictions\n\n_None found._" in render_markdown(a, [], "s")
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_render.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement the schema, the fixture and the renderers**

The Markdown card follows the AHRU example from the conversation:
- Header line: customer · division · RFQ no · due date · submission mode.
- `**Fit: <verdict>**` followed by the reasons as bullets.
- `##` sections in the order the first test checks.
- Lists of objects render as Markdown tables, with a source column.

HTML is a self-contained page with inline CSS (no external assets), built with `html.escape` on every value, so it can be pasted into Outlook. Don't use a Markdown library.

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `.venv/Scripts/python -m pytest tests/test_render.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add bidtriage/schema.py bidtriage/render.py tests/fixtures.py tests/test_render.py
git commit -m "feat: BidAssessment schema and Markdown/HTML card"
```

---

### Task 4: Analyzer (the Claude call) and system prompt

**Files:**
- Create: `bidtriage/analyzer.py`, `prompts/system.md`
- Test: `tests/test_analyzer.py`

**Interfaces:**
- Consumes: `Bid` (Task 1), content blocks (Task 2), `BidAssessment` (Task 3), `prompts/capability_profile.md` (exists).
- Produces:
  - `class AnalysisError(Exception)`
  - `build_request(bid: Bid, blocks: list[dict], *, model: str, effort: str, today: date, system_prompt: str, profile: str) -> dict`. Returns the kwargs for `client.messages.stream`, apart from `output_format`.
  - `analyze(bid: Bid, blocks: list[dict], *, client=None, model="claude-opus-5-5", effort="high", today: date | None = None) -> BidAssessment`. It reads both prompt files from `prompts/` next to the package root, and creates `anthropic.Anthropic()` when `client` is None.

- [ ] **Step 1: Write the failing tests**

```python
def test_build_request_shape():
    req = build_request(bid, blocks, model="claude-opus-5-5", effort="high", today=date(2026,10,21),
                        system_prompt="SYS", profile="PROFILE")
    assert req["model"] == "claude-opus-5-5"
    assert req["max_tokens"] == 64000
    assert req["output_config"] == {"effort": "high"}
    assert "thinking" not in req
    assert req["extra_headers"] == {"anthropic-beta": "server-side-fallback-2026-07-01"}
    assert req["extra_body"] == {"fallbacks": "default"}
    assert "SYS" in req["system"] and "PROFILE" in req["system"]
    content = req["messages"][0]["content"]
    assert content[:len(blocks)] == blocks            # documents before the text
    assert content[-1]["type"] == "text" and bid.subject in content[-1]["text"]

def test_build_request_includes_today():
    req = build_request(bid, [], model="m", effort="high", today=date(2026,10,21), system_prompt="", profile="")
    assert "2026-10-21" in req["messages"][0]["content"][-1]["text"]

def test_analyze_returns_parsed_output():
    client = FakeClient(stop_reason="end_turn", parsed=sample_assessment())
    assert analyze(bid, [], client=client, today=date(2026,10,21)).rfq_number == sample_assessment().rfq_number
    assert client.last_kwargs["output_format"] is BidAssessment

@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_analyze_raises_on_bad_stop_reason(reason):
    with pytest.raises(AnalysisError, match=reason):
        analyze(bid, [], client=FakeClient(stop_reason=reason, parsed=None), today=date(2026,10,21))
```

`FakeClient` is defined in the test file: `.messages.stream(**kw)` records `kw` and returns a context manager whose `get_final_message()` returns an object with `stop_reason` and `parsed_output`.

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_analyzer.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Write `prompts/system.md`**

The prompt must state:
- Role: bid analyst for Rug-Rel SBU-2, producing a triage card for the head of the power supply team.
- Read every attached document. Cite a source for every factual item as `<filename> p.<n>` (or `<filename>` for spreadsheets or the email body).
- Compare the due date with today's date (given in the user message). If it has passed or is within 3 days, put that first in `questions_for_reviewer`.
- Technical risks: flag specs that are hard to meet together, with a short engineering reason. Example of the expected depth: hold-up energy versus available volume. Do not invent specs.
- Contradictions: inconsistencies between or within documents (rail lists, standard revisions, quantities, dates).
- Commercial red flags: IPR and source-code handover, payment timing, liquidated damages, warranty and support length, fixed pricing, security deposits and bank guarantees. Terms that the capability profile lists as previously accepted are still listed, but noted as "previously accepted".
- Fit verdict: judge against the capability profile only. Any `[CONFIRM]` item the verdict depends on makes that reason "unclear", never assumed.
- Questions for reviewer: phrase missing information using the profile's MIR checklist.
- Write `"not stated"` for missing scalars. Never guess dates, quantities or values.

- [ ] **Step 4: Implement `build_request` and `analyze` in `bidtriage/analyzer.py`**

`system` = system prompt + `"\n\n# Capability profile\n\n"` + profile. The user content is the blocks followed by one text block containing:
- `Today's date: YYYY-MM-DD`
- the email's From, Date and Subject
- the email body
- the line `Attached documents: <comma-separated titles>`

`analyze` wraps the stream:
- `stop_reason` in `("refusal", "max_tokens")` → raise `AnalysisError(f"Claude stopped with {reason}; no card written")`.
- Catch `anthropic.APIStatusError` and `anthropic.APIConnectionError` and re-raise as `AnalysisError` with the status code and message. The SDK already retries 429 and 5xx errors twice.

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `.venv/Scripts/python -m pytest tests/test_analyzer.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add bidtriage/analyzer.py prompts/system.md tests/test_analyzer.py
git commit -m "feat: Claude analyzer with structured output and refusal fallback"
```

---

### Task 5: CLI and end-to-end run

**Files:**
- Create: `triage.py`, `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `load_bid`, `to_content_blocks`, `PayloadTooLarge`, `analyze`, `AnalysisError`, `render_markdown`, `render_html`.
- Produces:
  - `output_dir(base: Path, a: BidAssessment, subject: str, today: date) -> Path`: `base / f"{today:%Y-%m-%d}_{slug}"`, where `slug` is built from `rfq_number`. If `rfq_number` is `"not stated"`, the slug comes from the subject instead. Lowercase, runs of characters outside `[a-z0-9]` become `-`, at most 60 characters.
  - `main(argv: list[str] | None = None) -> int`
    - Args: `path`, `--model`, `--effort` (choices `low medium high xhigh max`), `--out` (default `out`).
    - Writes `card.md`, `card.html` and `assessment.json` (`model_dump_json(indent=2)` plus a `skipped_files` list).
    - Prints the three paths and returns 0.
    - On `ValueError`, `PayloadTooLarge` or `AnalysisError`: prints `error: <message>` to stderr and returns 1. No files are written.

- [ ] **Step 1: Write the failing tests**

```python
def test_output_dir_slug_is_filesystem_safe(tmp_path):
    a = sample_assessment()   # rfq_number "HAL/HYD/IMM-INDG/M1/PSM-AHRU/2026/01"
    d = output_dir(tmp_path, a, "subj", date(2026,10,21))
    assert d.name == "2026-10-21_hal-hyd-imm-indg-m1-psm-ahru-2026-01"

def test_main_writes_three_files(tmp_path, monkeypatch):
    # folder bid with email.txt + a.pdf; monkeypatch triage.analyze to return sample_assessment()
    assert main([str(bid_dir), "--out", str(tmp_path / "out")]) == 0
    files = sorted(p.name for p in next((tmp_path / "out").iterdir()).iterdir())
    assert files == ["assessment.json", "card.html", "card.md"]

def test_main_reports_analysis_error_and_writes_nothing(tmp_path, monkeypatch, capsys):
    # monkeypatch triage.analyze to raise AnalysisError("Claude stopped with refusal; no card written")
    assert main([str(bid_dir), "--out", str(tmp_path / "out")]) == 1
    assert "error: Claude stopped with refusal" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `.venv/Scripts/python -m pytest tests/test_cli.py -v`
Expected: FAIL (ImportError).

- [ ] **Step 3: Implement `triage.py`, then write `README.md`**

The README covers setup (venv, `pip install -r requirements.txt`, `ANTHROPIC_API_KEY` or `ant auth login`), usage (`python triage.py samples/ahru-hal-hyd`), the output files, and where to edit `prompts/`.

- [ ] **Step 4: Run the full suite**

Run: `.venv/Scripts/python -m pytest -v`
Expected: all 22 tests pass.

- [ ] **Step 5: Commit**

```bash
git add triage.py README.md tests/test_cli.py
git commit -m "feat: triage CLI writing card.md, card.html, assessment.json"
```

- [ ] **Step 6: Live run on the AHRU bid (costs API credits, needs credentials)**

Run: `.venv/Scripts/python triage.py samples/ahru-hal-hyd`
Expected: exit code 0, and three files in `out/2026-10-21_hal-hyd-imm-indg-m1-psm-ahru-2026-01/`.

- [ ] **Step 7: Check `card.md` against spec success criterion 1**

The card must mention each of these, with sources:
- the 100 ms hold-up as a technical risk
- the 3 VPEL rail missing from the output list
- the MIL-STD-461C vs 461E mismatch
- IPR, source code and Gerber handover
- payment only after development completion or certification
- 15-year obsolescence support with redesign at the vendor's cost
- manual tender-box submission
- ≥50% local content
- the 13 Oct deadline already passed

Record which items were hit and missed in the final report. If items are missed, adjust `prompts/system.md`, re-run, and commit the prompt change on its own.
