from datetime import date
from types import SimpleNamespace

import pytest

from bidtriage.analyzer import AnalysisError, analyze, build_request
from bidtriage.attachments import Skipped
from bidtriage.models import Bid
from tests.fixtures import sample_assessment

TODAY = date(2026, 10, 21)

bid = Bid(
    subject="AHRU Power Supply Requirement- HAL HYDERABAD",
    sender="imran khan <imran.khan@rugrel.com>",
    date="Wednesday, October 7, 2026 18:06",
    body="Please check the feasibility.",
)
blocks = [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "AA=="},
           "title": "rfq.pdf"}]
VALID_JSON = sample_assessment().model_dump_json()


def text(t):
    return SimpleNamespace(type="text", text=t)


class FakeStream:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


class FakeClient:
    def __init__(self, stop_reason, content):
        self.last_kwargs = None
        self._message = SimpleNamespace(stop_reason=stop_reason, content=content)
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeStream(self._message)


def test_build_request_shape():
    req = build_request(bid, blocks, [], model="claude-opus-5-5", effort="high", today=TODAY,
                        system_prompt="SYS", profile="PROFILE")
    assert req["model"] == "claude-opus-5-5"
    assert req["max_tokens"] == 64000
    assert req["output_config"]["effort"] == "high"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert "rfq_number" in req["output_config"]["format"]["schema"]["properties"]
    assert "output_format" not in req
    assert "thinking" not in req
    assert req["extra_headers"] == {"anthropic-beta": "server-side-fallback-2026-07-01"}
    assert req["extra_body"] == {"fallbacks": "default"}
    assert "SYS" in req["system"] and "PROFILE" in req["system"]
    content = req["messages"][0]["content"]
    assert content[: len(blocks)] == blocks
    assert content[-1]["type"] == "text"
    assert bid.subject in content[-1]["text"]
    assert "rfq.pdf" in content[-1]["text"]


def test_build_request_includes_today():
    req = build_request(bid, [], [], model="m", effort="high", today=TODAY, system_prompt="", profile="")
    assert "2026-10-21" in req["messages"][0]["content"][-1]["text"]


def test_build_request_names_unreadable_attachments():
    req = build_request(bid, [], [Skipped("Annexure-7.docx", "unsupported file type .docx")],
                        model="m", effort="high", today=TODAY, system_prompt="", profile="")
    msg = req["messages"][0]["content"][-1]["text"]
    assert "Attached but not readable by this tool: Annexure-7.docx" in msg
    assert "do not report these as missing" in msg


def test_analyze_returns_validated_assessment():
    client = FakeClient("end_turn", [text(VALID_JSON)])
    assert analyze(bid, [], client=client, today=TODAY).rfq_number == sample_assessment().rfq_number


def test_analyze_uses_text_after_last_fallback_block():
    content = [text('{"customer": "Hindustan Aer'), SimpleNamespace(type="fallback"), text(VALID_JSON)]
    result = analyze(bid, [], client=FakeClient("end_turn", content), today=TODAY)
    assert result.customer == sample_assessment().customer


def test_analyze_invalid_json_raises_analysis_error():
    with pytest.raises(AnalysisError, match="not a valid assessment"):
        analyze(bid, [], client=FakeClient("end_turn", [text('{"customer": "HAL"')]), today=TODAY)


def test_analyze_missing_credentials_gives_setup_hint():
    class NoAuthClient:
        def __init__(self):
            self.messages = SimpleNamespace(stream=self._stream)

        def _stream(self, **kwargs):
            raise TypeError('"Could not resolve authentication method. Expected one of api_key, auth_token"')

    with pytest.raises(AnalysisError, match="ANTHROPIC_API_KEY"):
        analyze(bid, [], client=NoAuthClient(), today=TODAY)


@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_analyze_raises_on_bad_stop_reason(reason):
    # Partial JSON, as a truncated or refused stream would leave it.
    with pytest.raises(AnalysisError, match=reason):
        analyze(bid, [], client=FakeClient(reason, [text('{"customer": "Hind')]), today=TODAY)
