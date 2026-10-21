from bidtriage.attachments import Skipped
from bidtriage.render import render_html, render_markdown
from tests.fixtures import sample_assessment


def test_markdown_card_sections_in_order():
    md = render_markdown(sample_assessment(), [], "AHRU Power Supply Requirement")
    order = ["Fit:", "Summary", "Key specs", "Quantities", "Technical risks", "Contradictions",
             "Commercial red flags", "Eligibility", "Timeline", "Questions for reviewer", "Documents"]
    positions = [md.index(h) for h in order]
    assert positions == sorted(positions)
    assert "HAL/HYD/IMM-INDG/M1/PSM-AHRU/2026/01" in md
    assert "RFQ_TenderDocument_PSMAHRU.pdf p.9" in md


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
