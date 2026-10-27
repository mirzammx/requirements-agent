import pytest

from bidtriage.draft_schema import ClauseResponse, ComplianceSection, FormRow
from bidtriage.guards import apply_guards
from bidtriage.profile import PROFILE_KEYS, load_profile
from tests.draft_fixtures import sample_draft


def _draft_with(*clauses, rows=()):
    d = sample_draft()
    d.sections = [ComplianceSection(heading="Part-B", clauses=list(clauses))]
    d.compliance_form_rows = list(rows)
    return d


def test_missing_profile_fields_are_unknown(tmp_path):
    p = tmp_path / "profile.toml"
    p.write_text('company_name = "Rug-Rel"\n', encoding="utf-8")
    prof = load_profile(p)
    assert prof["company_name"] == "Rug-Rel"
    assert prof["gstin"] == ""
    assert set(PROFILE_KEYS) <= set(prof)
    assert load_profile(tmp_path / "missing.toml")["company_name"] == ""


def test_review_without_placeholder_is_wrapped():
    c = ClauseResponse(ref="7.2", requirement="Hold-up 100 ms", status="review",
                       response="confirm feasibility", source="p.9")
    out = apply_guards(_draft_with(c), {k: "" for k in PROFILE_KEYS})
    assert out.sections[0].clauses[0].response == "[[REVIEW: confirm feasibility]]"


def test_unbacked_certification_claim_downgraded():
    c = ClauseResponse(ref="13", requirement="QMS as per HAL/AS9100/ISO9001", status="complied",
                       response="Complied", source="p.4")
    out = apply_guards(_draft_with(c), {k: "" for k in PROFILE_KEYS})
    clause = out.sections[0].clauses[0]
    assert clause.status == "review"
    assert "[[CONFIRM:" in clause.response and "AS9100" in clause.response


def test_backed_certification_claim_kept():
    profile = {k: "" for k in PROFILE_KEYS} | {"as9100": "AS9100D cert no. X", "iso_9001": "ISO 9001:2015"}
    c = ClauseResponse(ref="13", requirement="QMS as per HAL/AS9100/ISO9001", status="complied",
                       response="Complied", source="p.4")
    out = apply_guards(_draft_with(c), profile)
    assert out.sections[0].clauses[0].status == "complied"


def test_msec_is_not_mistaken_for_mse():
    c = ClauseResponse(ref="5", requirement="Hold up time 100 msec", status="complied",
                       response="Complied", source="p.9")
    out = apply_guards(_draft_with(c), {k: "" for k in PROFILE_KEYS})
    assert out.sections[0].clauses[0].status == "complied"


def test_form_row_mse_claim_without_udyam_becomes_placeholder():
    row = FormRow(sno="5", term="MSE vendor should mention MSE details (Regn. No ...)", response="Y")
    out = apply_guards(_draft_with(rows=[row]), {k: "" for k in PROFILE_KEYS})
    assert "[[CONFIRM:" in out.compliance_form_rows[0].response


def test_claim_in_response_or_noted_status_is_caught():
    blank = {k: "" for k in PROFILE_KEYS}
    in_response = ClauseResponse(ref="13", requirement="Vendor shall have an approved QMS", status="complied",
                                 response="Complied. Rug-Rel is AS9100D certified.", source="p.4")
    noted = ClauseResponse(ref="14", requirement="Bidder shall be AS9100 certified", status="noted",
                           response="Noted.", source="p.4")
    out = apply_guards(_draft_with(in_response, noted), blank)
    for clause in out.sections[0].clauses:
        assert clause.status == "review"
        assert "[[CONFIRM: Rug-Rel AS9100" in clause.response


def test_form_row_with_other_placeholder_still_gets_confirm():
    row = FormRow(sno="5", term="MSE registration details", response="Y [[MLC %]]")
    out = apply_guards(_draft_with(rows=[row]), {k: "" for k in PROFILE_KEYS})
    assert "[[MLC %]]" in out.compliance_form_rows[0].response
    assert "[[CONFIRM: Rug-Rel MSE/Udyam registration" in out.compliance_form_rows[0].response


@pytest.mark.parametrize("wording", ["ISO-9001 certified QMS", "AS-9100 QMS", "registered vendor of HAL",
                                     "registered with BEL", "Udyog Aadhaar memorandum", "NSIC registered"])
def test_common_certification_wordings_are_caught(wording):
    c = ClauseResponse(ref="x", requirement=wording, status="complied", response="Complied", source="p.1")
    out = apply_guards(_draft_with(c), {k: "" for k in PROFILE_KEYS})
    assert out.sections[0].clauses[0].status == "review"


def test_control_characters_are_stripped():
    c = ClauseResponse(ref="1", requirement="Spec\x0c page break", status="complied", response="Ok\x07",
                       source="p.1")
    out = apply_guards(_draft_with(c), {k: "" for k in PROFILE_KEYS})
    assert out.sections[0].clauses[0].requirement == "Spec page break"
    assert out.sections[0].clauses[0].response == "Ok"