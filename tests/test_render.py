from bidtriage.attachments import Skipped
from bidtriage.render import render_html, render_markdown
from bidtriage.schema import RedFlag, Risk
from tests.fixtures import sample_assessment

# Decision-first order: what to decide, then why, then reference material.
ORDER = ["Fit:", "Decisions needed", "Summary", "Technical risks", "Commercial red flags",
         "Contradictions", "Key specs", "Quantities", "Eligibility", "Timeline", "Documents"]


def test_markdown_card_sections_in_decision_first_order():
    md = render_markdown(sample_assessment(), [], "AHRU Power Supply Requirement")
    positions = [md.index(h) for h in ORDER]
    assert positions == sorted(positions)
    assert "HAL/HYD/IMM-INDG/M1/PSM-AHRU/2026/01" in md
    assert "RFQ_TenderDocument_PSMAHRU.pdf p.9" in md


def test_html_card_sections_in_decision_first_order():
    html = render_html(sample_assessment(), [], "s")
    positions = [html.index(h) for h in ORDER]
    assert positions == sorted(positions)


def test_risks_sorted_high_first():
    a = sample_assessment()
    a.technical_risks = [
        Risk(risk="Low thing", why_it_matters="x", severity="low", source="s"),
        Risk(risk="High thing", why_it_matters="x", severity="high", source="s"),
        Risk(risk="Medium thing", why_it_matters="x", severity="medium", source="s"),
    ]
    for out in (render_markdown(a, [], "s"), render_html(a, [], "s")):
        assert out.index("High thing") < out.index("Medium thing") < out.index("Low thing")


def test_previously_accepted_terms_are_tagged_and_listed_after_new_ones():
    a = sample_assessment()
    a.commercial_red_flags = [
        RedFlag(term="IPR to HAL", implication="Handover of Gerbers (previously accepted).", source="s"),
        RedFlag(term="Payment after certification", implication="Self-fund 18 months.", source="s"),
    ]
    md = render_markdown(a, [], "s")
    assert md.index("Payment after certification") < md.index("IPR to HAL")
    assert "previously accepted" in md
    assert "tag-accepted" in render_html(a, [], "s")


def test_card_lists_unread_files():
    md = render_markdown(sample_assessment(), [Skipped("spec.docx", "unsupported file type .docx")], "s")
    assert "Not read" in md
    assert "spec.docx" in md
    assert "unsupported file type .docx" in md


def test_html_escapes_content():
    a = sample_assessment()
    a.summary = "<script>x</script>"
    html = render_html(a, [], "s")
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html


def test_empty_lists_render_none_marker():
    a = sample_assessment()
    a.contradictions = []
    assert "Contradictions\n\n_None found._" in render_markdown(a, [], "s")
