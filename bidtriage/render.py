"""Render a BidAssessment as a Markdown card and a self-contained HTML card."""

from html import escape

from pydantic import BaseModel

from bidtriage.attachments import Skipped
from bidtriage.schema import BidAssessment

NONE_FOUND = "None found."

# (heading, attribute, columns as (label, field))
TABLE_SECTIONS: list[tuple[str, str, list[tuple[str, str]]]] = [
    ("Key specs", "key_specs", [("Parameter", "parameter"), ("Value", "value"), ("Source", "source")]),
    ("Quantities", "quantities", [("Phase", "phase"), ("Item", "item"), ("Qty", "qty"),
                                  ("Firm / anticipated", "firm_or_anticipated"), ("Source", "source")]),
    ("Technical risks", "technical_risks", [("Severity", "severity"), ("Risk", "risk"),
                                            ("Why it matters", "why_it_matters"), ("Source", "source")]),
    ("Contradictions", "contradictions", [("Issue", "issue"), ("Source", "source")]),
    ("Commercial red flags", "commercial_red_flags", [("Term", "term"), ("Implication", "implication"),
                                                      ("Source", "source")]),
    ("Eligibility", "eligibility", [("Requirement", "requirement"), ("Source", "source")]),
    ("Timeline", "timeline", [("Milestone", "milestone"), ("When", "when"), ("Source", "source")]),
]


def _header_line(a: BidAssessment) -> str:
    return " · ".join([a.customer, a.division, f"RFQ {a.rfq_number}", f"Due {a.due_date}",
                       f"Submission: {a.submission_mode}"])


def _cell_md(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(a: BidAssessment, skipped: list[Skipped], email_subject: str) -> str:
    out = [f"# {a.title}", "", f"_{_header_line(a)}_", "", f"Email: {email_subject}", "",
           f"**Fit: {a.fit_verdict}**", ""]
    out += [f"- {r}" for r in a.fit_reasons] + ["", "## Summary", "", a.summary, ""]
    for heading, attr, cols in TABLE_SECTIONS:
        rows: list[BaseModel] = getattr(a, attr)
        out += [f"## {heading}", ""]
        if not rows:
            out += [f"_{NONE_FOUND}_", ""]
            continue
        out.append("| " + " | ".join(label for label, _ in cols) + " |")
        out.append("|" + "---|" * len(cols))
        for row in rows:
            out.append("| " + " | ".join(_cell_md(getattr(row, f)) for _, f in cols) + " |")
        out.append("")
    out += ["## Questions for reviewer", ""]
    out += [f"- {q}" for q in a.questions_for_reviewer] or [f"_{NONE_FOUND}_"]
    out += ["", "## Documents", "", "Read: " + (", ".join(a.documents_read) or "none")]
    if skipped:
        out += ["", "**Not read:**"] + [f"- {s.filename}: {s.reason}" for s in skipped]
    return "\n".join(out) + "\n"


CSS = """
body{font-family:Segoe UI,Arial,sans-serif;max-width:960px;margin:24px auto;padding:0 16px;color:#1a1a1a}
h1{font-size:22px;margin-bottom:4px}h2{font-size:16px;margin-top:24px;border-bottom:1px solid #ddd}
.meta{color:#555}.fit{display:inline-block;padding:4px 10px;border-radius:4px;font-weight:600}
.fit-strong{background:#d9f2e0}.fit-possible{background:#fff2cc}.fit-poor{background:#f8d7da}.fit-unclear{background:#e2e3e5}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{border:1px solid #ccc;padding:6px;text-align:left;vertical-align:top}
th{background:#f3f3f3}.src{color:#666;font-size:12px}.none{color:#777;font-style:italic}
"""


def render_html(a: BidAssessment, skipped: list[Skipped], email_subject: str) -> str:
    e = escape
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        f"<title>{e(a.title)}</title><style>{CSS}</style></head><body>",
        f"<h1>{e(a.title)}</h1><p class='meta'>{e(_header_line(a))}</p>",
        f"<p class='meta'>Email: {e(email_subject)}</p>",
        f"<p><span class='fit fit-{e(a.fit_verdict)}'>Fit: {e(a.fit_verdict)}</span></p>",
        "<ul>" + "".join(f"<li>{e(r)}</li>" for r in a.fit_reasons) + "</ul>",
        f"<h2>Summary</h2><p>{e(a.summary)}</p>",
    ]
    for heading, attr, cols in TABLE_SECTIONS:
        rows = getattr(a, attr)
        parts.append(f"<h2>{e(heading)}</h2>")
        if not rows:
            parts.append(f"<p class='none'>{NONE_FOUND}</p>")
            continue
        head = "".join(f"<th>{e(label)}</th>" for label, _ in cols)
        body = "".join(
            "<tr>" + "".join(
                f"<td class='src'>{e(str(getattr(r, f)))}</td>" if f == "source" else f"<td>{e(str(getattr(r, f)))}</td>"
                for _, f in cols
            ) + "</tr>"
            for r in rows
        )
        parts.append(f"<table><tr>{head}</tr>{body}</table>")
    parts.append("<h2>Questions for reviewer</h2>")
    parts.append("<ul>" + "".join(f"<li>{e(q)}</li>" for q in a.questions_for_reviewer) + "</ul>"
                 if a.questions_for_reviewer else f"<p class='none'>{NONE_FOUND}</p>")
    parts.append(f"<h2>Documents</h2><p>Read: {e(', '.join(a.documents_read) or 'none')}</p>")
    if skipped:
        parts.append("<p><strong>Not read:</strong></p><ul>"
                     + "".join(f"<li>{e(s.filename)}: {e(s.reason)}</li>" for s in skipped) + "</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)
