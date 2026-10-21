"""Render a BidAssessment as a Markdown card and a self-contained HTML card.

Layout is decision-first: verdict and open decisions, then risks and red flags,
then reference material (specs, quantities, eligibility, timeline).
"""

from html import escape

from bidtriage.attachments import Skipped
from bidtriage.schema import BidAssessment, RedFlag, Risk

NONE_FOUND = "None found."
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
SEVERITY_ICON = {"high": "🔴", "medium": "🟠", "low": "🟡"}


def _sorted_risks(a: BidAssessment) -> list[Risk]:
    return sorted(a.technical_risks, key=lambda r: SEVERITY_ORDER.get(r.severity, 3))


def _accepted(flag: RedFlag) -> bool:
    return "previously accepted" in flag.implication.lower()


def _sorted_flags(a: BidAssessment) -> list[RedFlag]:
    """New terms first; terms Rug-Rel has accepted before go last."""
    return sorted(a.commercial_red_flags, key=_accepted)


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


# ---------------------------------------------------------------- Markdown

def _cell(value: str) -> str:
    return _one_line(value).replace("|", "\\|")


def _md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return out + [""]


def render_markdown(a: BidAssessment, skipped: list[Skipped], email_subject: str) -> str:
    out = [
        f"# {a.title}", "",
        f"**{a.customer}** · {a.division}  ",
        f"RFQ `{a.rfq_number}` · **Due {a.due_date}** · Submission: {a.submission_mode}  ",
        f"Contact: {a.bid_contact}  ",
        f"Email: {email_subject}", "",
        f"## Fit: {a.fit_verdict.upper()}", "",
    ]
    out += [f"- {_one_line(r)}" for r in a.fit_reasons] + [""]

    out += ["## Decisions needed", ""]
    out += [f"{i}. {_one_line(q)}" for i, q in enumerate(a.questions_for_reviewer, 1)] or [f"_{NONE_FOUND}_"]
    out += ["", "## Summary", "", _one_line(a.summary), ""]

    out += ["## Technical risks", ""]
    for r in _sorted_risks(a):
        out += [f"- {SEVERITY_ICON.get(r.severity, '')} **{r.severity.upper()}: {_one_line(r.risk)}**  ",
                f"  {_one_line(r.why_it_matters)}  ", f"  _Source: {r.source}_", ""]
    if not a.technical_risks:
        out += [f"_{NONE_FOUND}_", ""]

    out += ["## Commercial red flags", ""]
    for f in _sorted_flags(a):
        tag = " `previously accepted`" if _accepted(f) else ""
        out += [f"- **{_one_line(f.term)}**{tag}: {_one_line(f.implication)} _({f.source})_"]
    out += [f"_{NONE_FOUND}_"] if not a.commercial_red_flags else []
    out += [""]

    out += ["## Contradictions", ""]
    out += [f"- {_one_line(c.issue)} _({c.source})_" for c in a.contradictions] or [f"_{NONE_FOUND}_"]
    out += ["", "---", ""]

    out += ["## Key specs", ""]
    out += _md_table(["Parameter", "Value", "Source"], [[s.parameter, s.value, s.source] for s in a.key_specs]) \
        if a.key_specs else [f"_{NONE_FOUND}_", ""]
    out += ["## Quantities", ""]
    out += _md_table(["Phase", "Item", "Qty", "Firm?", "Source"],
                     [[q.phase, q.item, q.qty, q.firm_or_anticipated, q.source] for q in a.quantities]) \
        if a.quantities else [f"_{NONE_FOUND}_", ""]
    out += ["## Eligibility", ""]
    out += [f"- {_one_line(e.requirement)} _({e.source})_" for e in a.eligibility] or [f"_{NONE_FOUND}_"]
    out += ["", "## Timeline", ""]
    out += _md_table(["Milestone", "When", "Source"], [[t.milestone, t.when, t.source] for t in a.timeline]) \
        if a.timeline else [f"_{NONE_FOUND}_", ""]

    out += ["## Documents", "", "Read: " + (", ".join(a.documents_read) or "none")]
    if skipped:
        out += ["", "**Not read:**"] + [f"- {s.filename}: {s.reason}" for s in skipped]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- HTML

CSS = """
:root{--bg:#f5f6f8;--card:#fff;--text:#1d2330;--muted:#5f6b7a;--line:#e3e6ea;--accent:#6b2fa3;
--high:#c62828;--high-bg:#fdecea;--med:#b26a00;--med-bg:#fff4e0;--low:#8a7a00;--low-bg:#fbf8dc;
--ok:#1b7f3b;--ok-bg:#e6f4ea;--ask-bg:#fff8e6;--ask-line:#f0c36d;--grey-bg:#eef0f3}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1d2128;--text:#e6e9ee;--muted:#9aa4b2;
--line:#2e3440;--accent:#b98be6;--high:#ff8a80;--high-bg:#3a1f1f;--med:#ffb74d;--med-bg:#3a2d17;
--low:#e6d96b;--low-bg:#34311a;--ok:#81c995;--ok-bg:#1d3324;--ask-bg:#332b17;--ask-line:#8a6d2a;--grey-bg:#2a2f37}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 "Segoe UI",system-ui,-apple-system,Arial,sans-serif}
.wrap{max-width:920px;margin:0 auto;padding:24px 16px 48px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px 22px;margin-bottom:16px}
.eyebrow{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);font-weight:600}
h1{font-size:22px;line-height:1.3;margin:4px 0 12px}
h2{font-size:16px;margin:0 0 12px;display:flex;align-items:center;gap:8px}
.count{font-size:12px;font-weight:600;color:var(--muted);background:var(--grey-bg);border-radius:10px;padding:1px 8px}
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px 20px;margin:0}
.facts dt{font-size:12px;color:var(--muted)}.facts dd{margin:0;font-weight:500;overflow-wrap:anywhere}
.due{color:var(--high);font-weight:700}
.verdict{display:flex;gap:16px;align-items:flex-start}
.badge{flex:none;font-weight:700;font-size:14px;padding:6px 14px;border-radius:999px;text-transform:uppercase}
.fit-strong{background:var(--ok-bg);color:var(--ok)}.fit-possible{background:var(--med-bg);color:var(--med)}
.fit-poor{background:var(--high-bg);color:var(--high)}.fit-unclear{background:var(--grey-bg);color:var(--muted)}
ul,ol{margin:0;padding-left:20px}li{margin:4px 0}
.ask{background:var(--ask-bg);border-color:var(--ask-line)}
.ask ol li{margin:8px 0}
.risk{border-left:4px solid var(--line);padding:10px 14px;margin:10px 0;border-radius:6px;background:var(--bg)}
.risk.high{border-color:var(--high)}.risk.medium{border-color:var(--med)}.risk.low{border-color:var(--low)}
.pill{display:inline-block;font-size:11px;font-weight:700;border-radius:4px;padding:1px 7px;margin-right:6px;
text-transform:uppercase;vertical-align:1px}
.pill.high{background:var(--high-bg);color:var(--high)}.pill.medium{background:var(--med-bg);color:var(--med)}
.pill.low{background:var(--low-bg);color:var(--low)}
.risk .title{font-weight:600}.risk p{margin:4px 0 0}
.src{display:block;font-size:12px;color:var(--muted);margin-top:3px}
.flags li{margin:10px 0}.flags .term{font-weight:600}
.tag-accepted{display:inline-block;font-size:11px;background:var(--grey-bg);color:var(--muted);border-radius:4px;
padding:1px 7px;margin-left:6px}
li.accepted{color:var(--muted)}
details{border-top:1px solid var(--line);padding:10px 0}details:first-of-type{border-top:0}
summary{cursor:pointer;font-weight:600;font-size:15px}summary .count{margin-left:6px}
details[open] summary{margin-bottom:10px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;font-size:12px;color:var(--muted);font-weight:600;border-bottom:1px solid var(--line);padding:6px 8px}
td{border-bottom:1px solid var(--line);padding:7px 8px;vertical-align:top}
td.src{font-size:12px;color:var(--muted);white-space:nowrap}
.tablewrap{overflow-x:auto}
.none{color:var(--muted);font-style:italic;margin:0}
@media print{body{background:#fff}.card{break-inside:avoid}details{display:block}}
"""


def _src(source: str) -> str:
    return f"<span class='src'>{escape(source)}</span>"


def _count(n: int) -> str:
    return f"<span class='count'>{n}</span>"


def _none() -> str:
    return f"<p class='none'>{NONE_FOUND}</p>"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(
            f"<td class='src'>{escape(c)}</td>" if i == len(row) - 1 else f"<td>{escape(c)}</td>"
            for i, c in enumerate(row)
        ) + "</tr>"
        for row in rows
    )
    return f"<div class='tablewrap'><table><tr>{head}</tr>{body}</table></div>"


def _section(title: str, n: int, inner: str, extra_class: str = "") -> str:
    return f"<section class='card {extra_class}'><h2>{escape(title)} {_count(n)}</h2>{inner}</section>"


def render_html(a: BidAssessment, skipped: list[Skipped], email_subject: str) -> str:
    e = escape
    facts = [("Customer", f"{a.customer}, {a.division}"), ("RFQ", a.rfq_number),
             ("Due date", a.due_date), ("Submission", a.submission_mode),
             ("Contact", a.bid_contact), ("Email", email_subject)]
    facts_html = "".join(
        f"<div><dt>{e(k)}</dt><dd{' class=due' if k == 'Due date' else ''}>{e(v)}</dd></div>" for k, v in facts
    )
    parts = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>{e(a.title)}</title><style>{CSS}</style></head><body><main class='wrap'>",
        f"<section class='card'><div class='eyebrow'>Bid triage card</div><h1>{e(a.title)}</h1>"
        f"<dl class='facts'>{facts_html}</dl></section>",
        f"<section class='card'><div class='verdict'><span class='badge fit-{e(a.fit_verdict)}'>"
        f"Fit: {e(a.fit_verdict)}</span><ul>" + "".join(f"<li>{e(r)}</li>" for r in a.fit_reasons)
        + "</ul></div></section>",
    ]

    asks = "".join(f"<li>{e(q)}</li>" for q in a.questions_for_reviewer)
    parts.append(_section("Decisions needed", len(a.questions_for_reviewer),
                          f"<ol>{asks}</ol>" if asks else _none(), "ask"))
    parts.append(_section("Summary", 1, f"<p style='margin:0'>{e(a.summary)}</p>").replace(_count(1), ""))

    risks = "".join(
        f"<div class='risk {e(r.severity)}'><div class='title'><span class='pill {e(r.severity)}'>"
        f"{e(r.severity)}</span>{e(r.risk)}</div><p>{e(r.why_it_matters)}</p>{_src(r.source)}</div>"
        for r in _sorted_risks(a)
    )
    parts.append(_section("Technical risks", len(a.technical_risks), risks or _none()))

    flags = "".join(
        f"<li class='{'accepted' if _accepted(f) else ''}'><span class='term'>{e(f.term)}</span>"
        + ("<span class='tag-accepted'>previously accepted</span>" if _accepted(f) else "")
        + f"<br>{e(f.implication)}{_src(f.source)}</li>"
        for f in _sorted_flags(a)
    )
    parts.append(_section("Commercial red flags", len(a.commercial_red_flags),
                          f"<ul class='flags'>{flags}</ul>" if flags else _none()))

    contra = "".join(f"<li>{e(c.issue)}{_src(c.source)}</li>" for c in a.contradictions)
    parts.append(_section("Contradictions", len(a.contradictions),
                          f"<ul class='flags'>{contra}</ul>" if contra else _none()))

    reference = [
        ("Key specs", len(a.key_specs), True,
         _table(["Parameter", "Value", "Source"], [[s.parameter, s.value, s.source] for s in a.key_specs])),
        ("Quantities", len(a.quantities), False,
         _table(["Phase", "Item", "Qty", "Firm?", "Source"],
                [[q.phase, q.item, q.qty, q.firm_or_anticipated, q.source] for q in a.quantities])),
        ("Eligibility", len(a.eligibility), False,
         "<ul>" + "".join(f"<li>{e(x.requirement)}{_src(x.source)}</li>" for x in a.eligibility) + "</ul>"),
        ("Timeline", len(a.timeline), False,
         _table(["Milestone", "When", "Source"], [[t.milestone, t.when, t.source] for t in a.timeline])),
    ]
    details = "".join(
        f"<details{' open' if is_open else ''}><summary>{e(title)} {_count(n)}</summary>"
        f"{body if n else _none()}</details>"
        for title, n, is_open, body in reference
    )
    parts.append(f"<section class='card'>{details}</section>")

    docs = f"<p style='margin:0'>Read: {e(', '.join(a.documents_read) or 'none')}</p>"
    if skipped:
        docs += ("<p style='margin:10px 0 4px'><strong>Not read:</strong></p><ul>"
                 + "".join(f"<li>{e(s.filename)}: {e(s.reason)}</li>" for s in skipped) + "</ul>")
    parts.append(_section("Documents", len(a.documents_read), docs))
    parts.append("</main></body></html>")
    return "\n".join(parts)
