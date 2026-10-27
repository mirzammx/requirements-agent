"""Local web app: buttons for shortlist -> decision -> triage -> card -> response -> download.

Run in Docker:  docker compose up web   then open http://localhost:8010
"""

import io
import json
import os
import re
import shutil
import threading
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_file, send_from_directory, url_for
from werkzeug.utils import secure_filename

import draft
import shortlist
import triage
from bidtriage.render import CSS
from bidtriage.shortlist_out import EXTRA_CSS
from bidtriage.web import jobs

ROOT = Path(__file__).resolve().parent
ID_RE = re.compile(r"^\d{8}-[0-9a-f]{6}$")
DECISIONS = ("Go", "No-go", "Ask")
EMAIL_SUFFIXES = {".msg", ".eml"}
STEP_TEXT = {
    "triage": "Reading the documents and writing the triage card (usually 1–2 minutes)…",
    "draft": "Drafting the response pack (about 5–10 minutes on Gemini)…",
    "shortlist": "Screening the tenders (a few minutes for 100 tenders)…",
}
FILE_NOTES = {"Technical_Compliance.docx": "Mahadevan: resolve every yellow REVIEW / DEVIATION",
              "Compliance_Statement.docx": "Buyer's compliance form",
              "Price_Bid.xlsx": "BD: enter unit prices and GST % in the yellow cells",
              "Declarations.docx": "Print on letterhead and sign",
              "PreBid_Queries.docx": "Clarification letter to the buyer",
              "Checklist.md": "Every document the RFQ requires"}


def _unique_name(original: str, taken: set[str]) -> str:
    """A safe file name that keeps the extension (even for non-English names) and never overwrites."""
    suffix = Path(original).suffix.lower()
    suffix = suffix if suffix[1:].isalnum() else ""
    stem = secure_filename(Path(original).stem) or "upload"
    name, n = f"{stem}{suffix}", 2
    while name in taken:
        name, n = f"{stem}_{n}{suffix}", n + 1
    return name


def _new_id() -> str:
    return f"{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:6]}"


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _default_provider() -> str:
    return "gemini" if os.environ.get("GEMINI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY") else "claude"


def create_app(data_dir: Path = ROOT / "data", samples_dir: Path = ROOT / "samples", sync_jobs: bool = False,
               allowed_hosts: set[str] = frozenset({"localhost:8010", "127.0.0.1:8010"})):
    app = Flask(__name__, template_folder=str(ROOT / "bidtriage" / "web" / "templates"))
    app.config.update(MAX_CONTENT_LENGTH=50 * 1024 * 1024, SYNC_JOBS=sync_jobs)
    bids_dir, lists_dir = Path(data_dir) / "bids", Path(data_dir) / "shortlists"
    for d in (bids_dir, lists_dir):
        if d.is_dir():
            jobs.recover([p for p in d.iterdir() if p.is_dir()])
    allowed_origins = {f"http://{h}" for h in allowed_hosts}

    @app.before_request
    def same_origin_only():
        # Another website open in the browser must not drive this app (paid AI calls) or read it
        # (DNS rebinding): require our own Host, and our own Origin/Referer on any POST that sends one.
        if request.host not in allowed_hosts:
            abort(400)
        if request.method == "POST":
            origin = request.headers.get("Origin") or ""
            referer = request.headers.get("Referer") or ""
            if origin and origin not in allowed_origins:
                abort(403)
            if not origin and referer and not any(referer.startswith(o + "/") for o in allowed_origins):
                abort(403)

    @app.context_processor
    def common():
        return {"css": CSS + EXTRA_CSS, "providers": ("claude", "gemini"), "default_provider": _default_provider()}

    def folder(kind_dir: Path, item_id: str) -> Path:
        path = kind_dir / item_id
        if not ID_RE.match(item_id) or not path.is_dir():
            abort(404)
        return path

    def samples() -> list[str]:
        if not Path(samples_dir).is_dir():
            return []
        return sorted(p.name for p in Path(samples_dir).iterdir() if p.is_dir())

    def listing(kind_dir: Path) -> list[dict]:
        if not kind_dir.is_dir():
            return []
        items = [{**_read_json(p / "meta.json", {"id": p.name, "title": p.name}), "status": jobs.read_status(p)}
                 for p in kind_dir.iterdir() if p.is_dir() and ID_RE.match(p.name)]
        return sorted(items, key=lambda m: m.get("created", ""), reverse=True)

    def index_page(error: str = "", status: int = 200):
        return render_template("index.html", bids=listing(bids_dir), shortlists=listing(lists_dir),
                               samples=samples(), error=error), status

    def provider_arg() -> str:
        p = request.form.get("provider", "")
        return p if p in ("claude", "gemini") else _default_provider()

    @app.get("/")
    def index():
        return index_page()

    # ---------------------------------------------------------------- bids

    @app.post("/bids")
    def create_bid():
        provider = provider_arg()
        sample = request.form.get("sample", "")
        files = [f for f in request.files.getlist("files") if f and f.filename]
        subject, body = request.form.get("subject", "").strip(), request.form.get("body", "").strip()
        if sample and sample not in samples():
            abort(400)
        if not sample and not files:
            return index_page("Add the bid documents (email .msg/.eml, PDFs, Excel) or pick a sample folder.", 400)
        if sum(Path(f.filename).suffix.lower() in EMAIL_SUFFIXES for f in files) > 1:
            return index_page("Upload one email file (.msg or .eml) per bid; add its documents alongside it.", 400)

        bid_id = _new_id()
        bid = bids_dir / bid_id
        inp = bid / "input"
        inp.mkdir(parents=True)
        if sample:
            shutil.copytree(Path(samples_dir) / sample, inp, dirs_exist_ok=True)
        has_email = any(Path(f.filename).suffix.lower() in EMAIL_SUFFIXES for f in files)
        typed = (subject or body) and not has_email
        taken = {p.name for p in inp.iterdir()} | ({"email.txt"} if typed else set())
        for f in files:
            name = _unique_name(f.filename, taken)
            taken.add(name)
            f.save(inp / name)
        if typed and not (inp / "email.txt").exists():
            (inp / "email.txt").write_text(f"Subject: {subject}\n\n{body}\n", encoding="utf-8")

        # The folder loader handles one email file plus extra documents, or documents plus email.txt.
        bid_input = inp
        title = subject or sample or (files[0].filename if files else bid_id)
        meta = {"id": bid_id, "title": title, "created": f"{datetime.now():%Y-%m-%d %H:%M}", "provider": provider,
                "input": str(bid_input.relative_to(bid))}
        (bid / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        jobs.start(bid, "triage", lambda: triage.run_triage(bid_input, provider=provider, out_dir=bid / "card"),
                   sync=app.config["SYNC_JOBS"])
        return redirect(url_for("show_bid", bid_id=bid_id))

    @app.get("/bids/<bid_id>")
    def show_bid(bid_id):
        bid = folder(bids_dir, bid_id)
        status = jobs.read_status(bid)
        response = bid / "card" / "response"
        summary = _read_json(response / "summary.json", {})
        files = [{"name": n, "count": c, "note": FILE_NOTES.get(n, ""), "exists": (response / n).is_file()}
                 for n, c in summary.items()]
        return render_template("bid.html", meta=_read_json(bid / "meta.json", {"id": bid_id, "title": bid_id}),
                               status=status, step_text=STEP_TEXT.get(status.get("step", ""), "Working…"),
                               has_card=(bid / "card" / "card.html").is_file(),
                               can_draft=(bid / "card" / "assessment.json").is_file(), files=files,
                               has_saved_draft=(response / "draft.json").is_file(),
                               msg=request.args.get("msg", ""))

    @app.get("/bids/<bid_id>/card")
    def bid_card(bid_id):
        card = folder(bids_dir, bid_id) / "card" / "card.html"
        if not card.is_file():
            abort(404)
        return send_file(card)

    @app.post("/bids/<bid_id>/triage")
    def retriage_bid(bid_id):
        bid = folder(bids_dir, bid_id)
        bid_input = bid / _read_json(bid / "meta.json", {}).get("input", "input")
        provider = provider_arg()
        started = jobs.start(bid, "triage",
                             lambda: triage.run_triage(bid_input, provider=provider, out_dir=bid / "card"),
                             sync=app.config["SYNC_JOBS"])
        return redirect(url_for("show_bid", bid_id=bid_id, msg="" if started else "A job is already running."))

    @app.post("/bids/<bid_id>/draft")
    def draft_bid(bid_id):
        bid = folder(bids_dir, bid_id)
        if not (bid / "card" / "assessment.json").is_file():
            abort(400)
        meta = _read_json(bid / "meta.json", {})
        bid_input = bid / meta.get("input", "input")
        provider = provider_arg()
        started = jobs.start(bid, "draft",
                             lambda: draft.run_draft(bid_input, bid / "card", provider=provider),
                             sync=app.config["SYNC_JOBS"])
        return redirect(url_for("show_bid", bid_id=bid_id, msg="" if started else "A job is already running."))

    @app.post("/bids/<bid_id>/rebuild")
    def rebuild_bid(bid_id):
        bid = folder(bids_dir, bid_id)
        saved = bid / "card" / "response" / "draft.json"
        if not saved.is_file():
            abort(400)
        bid_input = bid / _read_json(bid / "meta.json", {}).get("input", "input")
        started = jobs.start(bid, "draft",
                             lambda: draft.run_draft(bid_input, bid / "card", from_draft=saved),
                             sync=app.config["SYNC_JOBS"])
        return redirect(url_for("show_bid", bid_id=bid_id, msg="" if started else "A job is already running."))

    def response_files(bid: Path) -> list[str]:
        """Files of the current pack only: a document the latest draft did not need is never offered."""
        summary = _read_json(bid / "card" / "response" / "summary.json", {})
        return [n for n, c in summary.items()
                if (c is not None or n == "Checklist.md") and (bid / "card" / "response" / n).is_file()]

    @app.get("/bids/<bid_id>/files/<name>")
    def bid_file(bid_id, name):
        bid = folder(bids_dir, bid_id)
        if name not in response_files(bid):
            abort(404)
        return send_from_directory(bid / "card" / "response", name, as_attachment=True)

    @app.get("/bids/<bid_id>/response.zip")
    def bid_zip(bid_id):
        bid = folder(bids_dir, bid_id)
        names = response_files(bid)
        if not names:
            abort(404)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for n in names:
                z.write(bid / "card" / "response" / n, n)
        buf.seek(0)
        title = secure_filename(_read_json(bid / "meta.json", {}).get("title", bid_id)) or bid_id
        return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=f"{title}_response.zip")

    # ---------------------------------------------------------------- shortlists

    @app.post("/shortlists")
    def create_shortlist():
        provider = provider_arg()
        files = [f for f in request.files.getlist("files") if f and f.filename]
        if not files:
            return index_page("Choose one or more BidAssist 'Tender List' .xlsx files.", 400)
        run_id = _new_id()
        run = lists_dir / run_id
        inp = run / "input"
        inp.mkdir(parents=True)
        paths = []
        for f in files:
            path = inp / (secure_filename(f.filename) or "tender-list.xlsx")
            f.save(path)
            paths.append(path)
        meta = {"id": run_id, "title": ", ".join(f.filename for f in files),
                "created": f"{datetime.now():%Y-%m-%d %H:%M}", "provider": provider}
        (run / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        jobs.start(run, "shortlist",
                   lambda: shortlist.run_shortlist(paths, provider=provider, out_dir=run / "result"),
                   sync=app.config["SYNC_JOBS"])
        return redirect(url_for("show_shortlist", run_id=run_id))

    def shortlist_items(run: Path) -> list[dict]:
        return _read_json(run / "result" / "shortlist.json", [])

    @app.get("/shortlists/<run_id>")
    def show_shortlist(run_id):
        run = folder(lists_dir, run_id)
        status = jobs.read_status(run)
        items = shortlist_items(run)
        decisions = _read_json(run / "decisions.json", {})

        def key(i):
            d = i.get("days_left")
            return (0, d) if d is not None and d >= 0 else (1, -(d or 0)) if d is not None else (2, 0)

        groups = {c: sorted([i for i in items if i["category"] == c], key=key)
                  for c in ("sbu2_power", "manual_check", "other_product_line", "not_relevant")}
        return render_template("shortlist.html", meta=_read_json(run / "meta.json", {"id": run_id}),
                               status=status, step_text=STEP_TEXT["shortlist"], groups=groups,
                               decisions=decisions, total=len(items), msg=request.args.get("msg", ""))

    @app.post("/shortlists/<run_id>/decide")
    def decide(run_id):
        run = folder(lists_dir, run_id)
        tender_id, decision = request.form.get("tender_id", ""), request.form.get("decision", "")
        if decision not in DECISIONS or tender_id not in {i["tender_id"] for i in shortlist_items(run)}:
            abort(400)
        msg = ""
        with DECISION_LOCK:  # two quick clicks must not lose a decision or interleave workbook saves
            decisions = _read_json(run / "decisions.json", {})
            decisions[tender_id] = decision
            _atomic_write_text(run / "decisions.json", json.dumps(decisions, indent=2))
            try:
                _write_decision_to_xlsx(run / "result" / "shortlist.xlsx", tender_id, decision)
            except Exception:
                msg = ("Decision saved, but shortlist.xlsx could not be updated (is it open in Excel?). "
                       "Close it and click the decision again to copy it into the workbook.")
        return redirect(url_for("show_shortlist", run_id=run_id, msg=msg) + "#" + _anchor(tender_id))

    @app.get("/shortlists/<run_id>/files/<name>")
    def shortlist_file(run_id, name):
        run = folder(lists_dir, run_id)
        if name not in ("digest.html", "shortlist.xlsx") or not (run / "result" / name).is_file():
            abort(404)
        return send_from_directory(run / "result", name, as_attachment=name.endswith(".xlsx"))

    app.add_template_filter(_anchor, "anchor")

    return app


def _anchor(tender_id: str) -> str:
    return "t-" + re.sub(r"[^A-Za-z0-9]+", "-", tender_id).strip("-")


DECISION_LOCK = threading.Lock()


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _write_decision_to_xlsx(path: Path, tender_id: str, decision: str) -> None:
    import openpyxl

    wb = openpyxl.load_workbook(path)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    id_col, decision_col = headers.index("Tender Id"), headers.index("Decision")
    for row in ws.iter_rows(min_row=2):
        if row[id_col].value == tender_id:
            row[decision_col].value = decision
    tmp = path.with_name(path.stem + ".tmp.xlsx")
    wb.save(tmp)
    os.replace(tmp, path)


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=8000, debug=False, threaded=True)
