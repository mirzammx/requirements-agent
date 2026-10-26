import base64
from datetime import date
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from bidtriage import gemini_analyzer
from bidtriage.analyzer import AnalysisError
from bidtriage.attachments import Skipped
from bidtriage.gemini_analyzer import analyze_gemini, build_gemini_request, call_gemini
from bidtriage.models import Bid
from tests.fixtures import sample_assessment

TODAY = date(2026, 10, 21)
PDF = b"%PDF-1.4 test"
bid = Bid(subject="AHRU Power Supply Requirement- HAL HYDERABAD", sender="imran", date="7 Oct", body="Check.")
blocks = [
    {"type": "document", "title": "rfq.pdf",
     "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(PDF).decode()}},
    {"type": "text", "text": "=== price.xlsx / sheet Price ===\nPSM\t4"},
]


def response(text, finish="STOP"):
    return SimpleNamespace(text=text, prompt_feedback=None,
                           candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name=finish))])


class FakeGemini:
    def __init__(self, resp):
        self.last_kwargs = None
        self.models = SimpleNamespace(generate_content=self._generate)
        self._resp = resp

    def _generate(self, **kwargs):
        self.last_kwargs = kwargs
        return self._resp


def test_request_labels_each_pdf_and_sends_bytes():
    req = build_gemini_request(bid, blocks, [], model="gemini-3.8-flash", effort="high", today=TODAY,
                               system_prompt="SYS", profile="PROFILE")
    parts = req["contents"]
    assert parts[0].text == "=== Document: rfq.pdf ==="
    assert parts[1].inline_data.mime_type == "application/pdf"
    assert parts[1].inline_data.data == PDF
    assert "PSM\t4" in parts[2].text
    assert "2026-10-21" in parts[-1].text and bid.subject in parts[-1].text


def test_request_config_asks_for_assessment_json():
    req = build_gemini_request(bid, [], [Skipped("a.docx", "unsupported")], model="m", effort="high",
                               today=TODAY, system_prompt="SYS", profile="PROFILE")
    cfg = req["config"]
    assert req["model"] == "m"
    assert cfg.response_mime_type == "application/json"
    assert "rfq_number" in cfg.response_json_schema["properties"]
    assert "SYS" in cfg.system_instruction and "PROFILE" in cfg.system_instruction
    assert cfg.thinking_config.thinking_level.name == "HIGH"
    assert "a.docx" in req["contents"][-1].text


def test_analyze_gemini_returns_validated_assessment():
    client = FakeGemini(response(sample_assessment().model_dump_json()))
    result = analyze_gemini(bid, blocks, client=client, today=TODAY)
    assert result.rfq_number == sample_assessment().rfq_number


@pytest.mark.parametrize("finish", ["MAX_TOKENS", "SAFETY"])
def test_analyze_gemini_bad_finish_reason_raises(finish):
    with pytest.raises(AnalysisError, match=finish):
        analyze_gemini(bid, [], client=FakeGemini(response('{"customer": "H', finish)), today=TODAY)


def test_analyze_gemini_invalid_json_raises():
    with pytest.raises(AnalysisError, match="not a valid assessment"):
        analyze_gemini(bid, [], client=FakeGemini(response('{"customer": "H"}')), today=TODAY)


def test_analyze_gemini_missing_key_gives_setup_hint(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(AnalysisError, match="GEMINI_API_KEY"):
        analyze_gemini(bid, [], today=TODAY)


def test_analyze_gemini_rejects_oversized_inline_request(monkeypatch):
    monkeypatch.setattr(gemini_analyzer, "MAX_INLINE_BYTES", 5)
    with pytest.raises(AnalysisError, match="too large"):
        analyze_gemini(bid, blocks, client=FakeGemini(response("{}")), today=TODAY)


class Tiny(BaseModel):
    x: str


def test_call_gemini_validates_against_given_schema():
    client = FakeGemini(response('{"x": "hi"}'))
    result = call_gemini("SYS", [], "hello", Tiny, client=client, model="m", effort="low")
    assert result == Tiny(x="hi")
    cfg = client.last_kwargs["config"]
    assert cfg.system_instruction == "SYS"
    assert "x" in cfg.response_json_schema["properties"]
    assert cfg.thinking_config.thinking_level.name == "LOW"