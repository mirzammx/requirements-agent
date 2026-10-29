import pytest

from bidtriage.reply import build_reply
from tests.fixtures import sample_assessment

SIG = "On behalf of Mahadevan, SBU-2"


def test_go_reply_has_summary_risks_queries_and_pack():
    r = build_reply(sample_assessment(), "Go", pack_placeholders=47, signature=SIG)
    html = r["html"]
    assert "Feasible" in html
    assert sample_assessment().summary in html
    assert "100 ms hold-up" in html                                   # high technical risk
    assert "3 VPEL rail not in output list" in html                   # contradiction to raise with buyer
    assert "attached" in html and "47 placeholders" in html
    assert SIG in html
    assert "HAL/HYD/IMM-INDG/M1/PSM-AHRU/2026/01" in html


def test_no_go_reply_gives_reasons_and_no_pack():
    html = build_reply(sample_assessment(), "No-go", pack_placeholders=None, signature=SIG)["html"]
    assert "Not feasible" in html
    assert "28 V DC input and 3U form factor" in html                 # fit reason
    assert "100 ms hold-up" in html                                   # high risk as a reason
    assert "attached" not in html


def test_ask_reply_lists_open_questions():
    html = build_reply(sample_assessment(), "Ask", pack_placeholders=None, signature=SIG)["html"]
    assert "clarification" in html
    assert "Due date 13 Oct has passed" in html


def test_reply_html_escaped_and_text_plain():
    a = sample_assessment()
    a.summary = "<b>bold</b> & co"
    r = build_reply(a, "Go", pack_placeholders=3, signature=SIG)
    assert "<b>bold</b>" not in r["html"] and "&lt;b&gt;bold&lt;/b&gt; &amp; co" in r["html"]
    assert "<" not in r["text"].replace("<b>bold</b>", "") and "<b>bold</b> & co" in r["text"]


def test_unknown_decision_rejected():
    with pytest.raises(ValueError):
        build_reply(sample_assessment(), "Maybe", pack_placeholders=None, signature=SIG)
