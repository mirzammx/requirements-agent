from datetime import date
from types import SimpleNamespace

import pytest

from bidtriage.analyzer import AnalysisError, analyze, build_request
from bidtriage.models import Bid
from bidtriage.schema import BidAssessment
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
    def __init__(self, stop_reason, parsed):
        self.last_kwargs = None
        message = SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed)
        self.messages = SimpleNamespace(stream=self._stream)
        self._message = message

    def _stream(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeStream(self._message)


def test_build_request_shape():
    req = build_request(bid, blocks, model="claude-opus-5-5", effort="high", today=TODAY,
                        system_prompt="SYS", profile="PROFILE")
    assert req["model"] == "claude-opus-5-5"
    assert req["max_tokens"] == 64000
    assert req["output_config"] == {"effort": "high"}
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
    req = build_request(bid, [], model="m", effort="high", today=TODAY, system_prompt="", profile="")
    assert "2026-10-21" in req["messages"][0]["content"][-1]["text"]


def test_analyze_returns_parsed_output():
    client = FakeClient(stop_reason="end_turn", parsed=sample_assessment())
    result = analyze(bid, [], client=client, today=TODAY)
    assert result.rfq_number == sample_assessment().rfq_number
    assert client.last_kwargs["output_format"] is BidAssessment


@pytest.mark.parametrize("reason", ["refusal", "max_tokens"])
def test_analyze_raises_on_bad_stop_reason(reason):
    with pytest.raises(AnalysisError, match=reason):
        analyze(bid, [], client=FakeClient(stop_reason=reason, parsed=None), today=TODAY)
