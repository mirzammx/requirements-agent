import io
import json
import zipfile
from datetime import date

import openpyxl
import pytest

import draft
import shortlist
import triage
import webapp
from bidtriage.analyzer import AnalysisError
from bidtriage.bidassist import Tender
from bidtriage.shortlist_out import build_tracker
from bidtriage.shortlister import Shortlisted
from bidtriage.web import jobs
from tests.fixtures import sample_assessment

RESPONSE_FILES = {"Technical_Compliance.docx": 47, "Compliance_Statement.docx": 10, "Price_Bid.xlsx": 8,
                  "Checklist.md": None}


def fake_triage(path, *, out_dir, **kwargs):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "card.html").write_text("<html><body>CARD for HAL AHRU</body></html>", encoding="utf-8")
    (out_dir / "assessment.json").write_text(sample_assessment().model_dump_json(), encoding="utf-8")
    return out_dir


def fake_draft(path, card_dir, **kwargs):
    out = card_dir / "response"
    out.mkdir(parents=True, exist_ok=True)
    for name in RESPONSE_FILES:
        (out / name).write_bytes(b"content of " + name.encode())
    (out / "summary.json").write_text(json.dumps(RESPONSE_FILES), encoding="utf-8")
    return RESPONSE_FILES


ITEMS = [
    Shortlisted(Tender(tender_id="GEM/2026/B/8082649", authority="BEL", summary="Variable SMPS",
                       closing_date="05-Oct-2026"), "sbu2_power", "SBU-2", "high", "SMPS unit", 3),
    Shortlisted(Tender(tender_id="MES1", authority="MES", summary="Power supply to barriers"),
                "not_relevant", "none", "high", "Civil works", 2),
]


def fake_shortlist(paths, *, out_dir, **kwargs):
    out_dir.mkdir(parents=True, exist_ok=True)
    build_tracker(ITEMS).save(out_dir / "shortlist.xlsx")
    (out_dir / "digest.html").write_text("<html>digest</html>", encoding="utf-8")
    data = [{"tender_id": s.tender.tender_id, "authority": s.tender.authority, "summary": s.tender.summary,
             "closing_date": s.tender.closing_date, "category": s.category, "route_to": s.route_to,
             "confidence": s.confidence, "reason": s.reason, "days_left": s.days_left, "location": "",
             "amount": "", "emd": "", "tender_no": "", "corrigendum": False} for s in ITEMS]
    (out_dir / "shortlist.json").write_text(json.dumps(data), encoding="utf-8")
    return out_dir, ITEMS


@pytest.fixture
def env(tmp_path, monkeypatch):
    samples = tmp_path / "samples"
    (samples / "ahru-hal-hyd").mkdir(parents=True)
    (samples / "ahru-hal-hyd" / "email.txt").write_text("Subject: AHRU\n\nCheck.", encoding="utf-8")
    (samples / "ahru-hal-hyd" / "rfq.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(triage, "run_triage", fake_triage)
    monkeypatch.setattr(draft, "run_draft", fake_draft)
    monkeypatch.setattr(shortlist, "run_shortlist", fake_shortlist)
    app = webapp.create_app(data_dir=tmp_path / "data", samples_dir=samples, sync_jobs=True)
    return app.test_client(), tmp_path / "data"


def _new_bid(client, **data):
    form = {"provider": "gemini", "subject": "HAL AHRU", "body": "Check feasibility",
            "files": [(io.BytesIO(b"%PDF-1.4"), "RFQ Tender.pdf")]} | data
    resp = client.post("/bids", data=form, content_type="multipart/form-data")
    assert resp.status_code == 302, resp.data
    return resp.headers["Location"]


def test_dashboard_renders(env):
    client, _ = env
    html = client.get("/").get_data(as_text=True)
    assert "Screen BidAssist exports" in html and "New bid" in html
    assert "ahru-hal-hyd" in html


def test_upload_bid_runs_triage_and_shows_card(env):
    client, data = env
    url = _new_bid(client)
    html = client.get(url).get_data(as_text=True)
    assert "Generate response" in html and "/card" in html
    bid_dir = next((data / "bids").iterdir())
    assert (bid_dir / "input" / "RFQ_Tender.pdf").is_file()
    assert "Subject: HAL AHRU" in (bid_dir / "input" / "email.txt").read_text(encoding="utf-8")
    assert "CARD for HAL AHRU" in client.get(url + "/card").get_data(as_text=True)


def test_bid_from_sample_folder(env):
    client, data = env
    resp = client.post("/bids", data={"provider": "gemini", "sample": "ahru-hal-hyd"},
                       content_type="multipart/form-data")
    assert resp.status_code == 302
    bid_dir = next((data / "bids").iterdir())
    assert (bid_dir / "input" / "rfq.pdf").is_file()


def test_upload_without_files_errors(env):
    client, data = env
    resp = client.post("/bids", data={"provider": "gemini", "subject": "x"}, content_type="multipart/form-data")
    assert resp.status_code == 400
    assert "Add the bid documents" in resp.get_data(as_text=True)
    assert not (data / "bids").exists() or not any((data / "bids").iterdir())


def test_generate_response_lists_files_and_downloads(env):
    client, _ = env
    url = _new_bid(client)
    assert client.post(url + "/draft", data={"provider": "gemini"}).status_code == 302
    html = client.get(url).get_data(as_text=True)
    assert "Technical_Compliance.docx" in html and "47 placeholders" in html and "8 lines to price" in html
    assert client.get(url + "/files/Price_Bid.xlsx").data == b"content of Price_Bid.xlsx"


def test_zip_download(env):
    client, _ = env
    url = _new_bid(client)
    client.post(url + "/draft", data={"provider": "gemini"})
    resp = client.get(url + "/response.zip")
    names = zipfile.ZipFile(io.BytesIO(resp.data)).namelist()
    assert set(RESPONSE_FILES) <= set(names) and "summary.json" not in names


def test_download_rejects_traversal(env):
    client, _ = env
    url = _new_bid(client)
    client.post(url + "/draft", data={"provider": "gemini"})
    assert client.get(url + "/files/..%2F..%2Finput%2Femail.txt").status_code == 404
    assert client.get(url + "/files/../assessment.json").status_code == 404
    assert client.get("/bids/..%2F..%2Fetc/card").status_code == 404


def test_failed_job_shows_error(env, monkeypatch):
    client, _ = env

    def boom(*a, **k):
        raise AnalysisError("Gemini API error 503: high demand")

    monkeypatch.setattr(triage, "run_triage", boom)
    html = client.get(_new_bid(client)).get_data(as_text=True)
    assert "Gemini API error 503: high demand" in html
    assert 'http-equiv="refresh"' not in html


def test_running_job_page_refreshes(env):
    client, data = env
    url = _new_bid(client)
    bid_dir = next((data / "bids").iterdir())
    jobs.write_status(bid_dir, {"state": "running", "step": "draft"})
    html = client.get(url).get_data(as_text=True)
    assert 'http-equiv="refresh"' in html and "Drafting the response" in html


def test_double_submit_starts_one_job(env, monkeypatch):
    client, data = env
    url = _new_bid(client)
    bid_dir = next((data / "bids").iterdir())
    jobs.write_status(bid_dir, {"state": "running", "step": "draft"})
    calls = []
    monkeypatch.setattr(draft, "run_draft", lambda *a, **k: calls.append(1))
    client.post(url + "/draft", data={"provider": "gemini"})
    assert calls == []


def test_shortlist_upload_and_decide(env):
    client, data = env
    resp = client.post("/shortlists", data={"provider": "gemini",
                                            "files": [(io.BytesIO(b"PK"), "Power supply-Tender List.xlsx")]},
                       content_type="multipart/form-data")
    assert resp.status_code == 302
    url = resp.headers["Location"]
    html = client.get(url).get_data(as_text=True)
    assert "Variable SMPS" in html and "Go" in html and "Civil works" in html
    assert client.post(url + "/decide", data={"tender_id": "GEM/2026/B/8082649", "decision": "Go"}).status_code == 302
    run_dir = next((data / "shortlists").iterdir())
    assert json.loads((run_dir / "decisions.json").read_text())["GEM/2026/B/8082649"] == "Go"
    ws = openpyxl.load_workbook(run_dir / "result" / "shortlist.xlsx").active
    headers = [c.value for c in ws[1]]
    row = next(r for r in ws.iter_rows(min_row=2) if r[headers.index("Tender Id")].value == "GEM/2026/B/8082649")
    assert row[headers.index("Decision")].value == "Go"


def test_decide_unknown_tender_400(env):
    client, _ = env
    resp = client.post("/shortlists", data={"provider": "gemini", "files": [(io.BytesIO(b"PK"), "a.xlsx")]},
                       content_type="multipart/form-data")
    url = resp.headers["Location"]
    assert client.post(url + "/decide", data={"tender_id": "NOPE", "decision": "Go"}).status_code == 400
    assert client.post(url + "/decide", data={"tender_id": "GEM/2026/B/8082649", "decision": "Maybe"}
                       ).status_code == 400
