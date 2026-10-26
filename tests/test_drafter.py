from datetime import date

import pytest

import draft as draft_cli
from bidtriage import drafter
from bidtriage.draft_schema import ClauseResponse, ComplianceSection
from bidtriage.drafter import draft_response, draft_user_text
from bidtriage.models import Bid
from bidtriage.profile import PROFILE_KEYS
from tests.draft_fixtures import sample_draft
from tests.fixtures import sample_assessment

TODAY = date(2026, 10, 26)
BID = Bid(subject="AHRU Power Supply Requirement- HAL HYDERABAD", sender="imran", date="7 Oct", body="Check.")
PROFILE = {k: "" for k in PROFILE_KEYS} | {"company_name": "Rug-Rel Components & Systems Pvt Ltd"}


def test_user_text_contains_assessment_and_profile():
    text = draft_user_text(BID, [], [], sample_assessment(), PROFILE, TODAY)
    assert "2026-10-26" in text
    assert "HAL/HYD/IMM-INDG/M1/PSM-AHRU/2026/01" in text
    assert "100 ms hold-up" in text
    assert "Rug-Rel Components & Systems Pvt Ltd" in text
    assert '"gstin": ""' in text


def test_draft_response_applies_guards(monkeypatch):
    raw = sample_draft()
    raw.sections = [ComplianceSection(heading="Part-C", clauses=[
        ClauseResponse(ref="13", requirement="QMS per AS9100", status="complied", response="Complied", source="p.4")])]
    seen = {}

    def fake_call(system, blocks, text, schema, **kwargs):
        seen.update(kwargs, schema=schema, system=system)
        return raw

    monkeypatch.setitem(drafter.PROVIDERS, "claude", fake_call)
    out = draft_response(BID, [], [], sample_assessment(), provider="claude", today=TODAY, profile=PROFILE)
    assert out.sections[0].clauses[0].status == "review"
    assert seen["schema"].__name__ == "ResponseDraft"
    assert seen["model"] == "claude-opus-5-5"
    assert "never" in seen["system"].lower() and "price" in seen["system"].lower()


@pytest.fixture
def bid_and_card(tmp_path):
    bid = tmp_path / "bid"
    bid.mkdir()
    (bid / "email.txt").write_text("Subject: AHRU\n\nCheck.", encoding="utf-8")
    card = tmp_path / "card"
    card.mkdir()
    (card / "assessment.json").write_text(sample_assessment().model_dump_json(), encoding="utf-8")
    return bid, card


def test_cli_writes_response_files(monkeypatch, bid_and_card):
    bid, card = bid_and_card
    monkeypatch.setattr(draft_cli, "draft_response", lambda *a, **k: sample_draft())
    assert draft_cli.main([str(bid), "--card", str(card)]) == 0
    names = sorted(p.name for p in (card / "response").iterdir())
    assert names == ["Checklist.md", "Compliance_Statement.docx", "Declarations.docx", "PreBid_Queries.docx",
                     "Price_Bid.xlsx", "Technical_Compliance.docx", "draft.json"]


def test_cli_missing_card_errors(tmp_path, capsys, bid_and_card):
    bid, _ = bid_and_card
    assert draft_cli.main([str(bid), "--card", str(tmp_path / "nope")]) == 1
    assert "error:" in capsys.readouterr().err
