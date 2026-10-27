from datetime import date

from bidtriage import shortlister
from bidtriage.bidassist import Tender
from bidtriage.shortlister import RowVerdict, Verdicts, batch_text, classify

TODAY = date(2026, 10, 10)


def tenders(n):
    return [Tender(tender_id=f"T{i}", authority="BEL", summary=f"Item {i}", closing_date="16-Oct-2026")
            for i in range(n)]


def fake_provider(calls, drop=(), extra=()):
    def call(system, blocks, text, schema, **kwargs):
        ids = [line.split(" | ")[0].strip() for line in text.splitlines() if line.startswith("T")]
        calls.append(ids)
        verdicts = [RowVerdict(tender_id=i, category="sbu2_power", route_to="SBU-2", confidence="high",
                               reason="PSU") for i in ids if i not in drop]
        verdicts += [RowVerdict(tender_id=i, category="not_relevant", route_to="none", confidence="low",
                                reason="x") for i in extra]
        assert schema is Verdicts
        return Verdicts(verdicts=verdicts)
    return call


def test_rows_are_batched(monkeypatch):
    calls = []
    monkeypatch.setitem(shortlister.PROVIDERS, "claude", fake_provider(calls))
    out = classify(tenders(5), provider="claude", today=TODAY, batch_size=2)
    assert [len(c) for c in calls] == [2, 2, 1]
    assert [s.tender.tender_id for s in out] == ["T0", "T1", "T2", "T3", "T4"]


def test_missing_and_unknown_ids(monkeypatch):
    monkeypatch.setitem(shortlister.PROVIDERS, "claude", fake_provider([], drop={"T1"}, extra={"BOGUS"}))
    out = {s.tender.tender_id: s for s in classify(tenders(2), provider="claude", today=TODAY)}
    assert set(out) == {"T0", "T1"}
    assert out["T0"].category == "sbu2_power"
    assert out["T1"].category == "manual_check"


def test_days_left_and_closed(monkeypatch):
    monkeypatch.setitem(shortlister.PROVIDERS, "claude", fake_provider([]))
    ts = [Tender(tender_id="T0", closing_date="16-Oct-2026"), Tender(tender_id="T1", closing_date="01-Oct-2026"),
          Tender(tender_id="T2", closing_date="-")]
    out = {s.tender.tender_id: s for s in classify(ts, provider="claude", today=TODAY)}
    assert out["T0"].days_left == 6
    assert out["T1"].days_left == -9
    assert out["T2"].days_left is None


def test_batch_text_lists_rows_and_profile():
    t = Tender(tender_id="GEM/1", authority="DRDO", summary="Category: Ac Dc Power Supplies",
               description="Category: Ac Dc Power Supplies", keyword="power supply", amount="14.02 Lac")
    text = batch_text([t])
    assert "GEM/1 | DRDO | Category: Ac Dc Power Supplies" in text
    assert "keyword: power supply" in text
    assert "14.02 Lac" in text


def test_failed_batch_keeps_other_batches(monkeypatch):
    from bidtriage.analyzer import AnalysisError

    good = fake_provider([])
    state = {"n": 0}

    def flaky(system, blocks, text, schema, **kwargs):
        state["n"] += 1
        if state["n"] == 2:
            raise AnalysisError("Gemini API error 429: quota")
        return good(system, blocks, text, schema, **kwargs)

    monkeypatch.setitem(shortlister.PROVIDERS, "claude", flaky)
    out = {s.tender.tender_id: s for s in classify(tenders(4), provider="claude", today=TODAY, batch_size=2)}
    assert out["T0"].category == "sbu2_power" and out["T1"].category == "sbu2_power"
    assert out["T2"].category == "manual_check" and "Batch failed" in out["T2"].reason and "429" in out["T2"].reason


def test_all_batches_failing_raises(monkeypatch):
    import pytest

    from bidtriage.analyzer import AnalysisError

    def broken(*a, **k):
        raise AnalysisError("no key")

    monkeypatch.setitem(shortlister.PROVIDERS, "claude", broken)
    with pytest.raises(AnalysisError, match="no key"):
        classify(tenders(3), provider="claude", today=TODAY, batch_size=2)