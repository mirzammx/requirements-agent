"""The reply to BD after Mahadevan's decision, built from the triage card by code.

No AI call and nothing invented: every line comes from the assessment. Returned as escaped HTML
(for the Outlook draft) and plain text.
"""

from html import escape

from bidtriage.schema import BidAssessment

DECISIONS = ("Go", "No-go", "Ask")
MAX_ITEMS = 6


def _risks(a: BidAssessment, severities: tuple[str, ...]) -> list[str]:
    return [f"{r.risk}: {r.why_it_matters}" for r in a.technical_risks if r.severity in severities][:MAX_ITEMS]


def build_reply(a: BidAssessment, decision: str, *, pack_placeholders: int | None, signature: str) -> dict:
    if decision not in DECISIONS:
        raise ValueError(f"unknown decision {decision!r}")
    ref = f"{a.title} ({a.rfq_number}, {a.customer}, due {a.due_date})"
    blocks: list[tuple[str, object]] = [("p", "Hi,")]

    if decision == "Go":
        blocks.append(("p", f"Feasible: we will bid for {ref}."))
        blocks.append(("p", a.summary))
        if risks := _risks(a, ("high", "medium")):
            blocks += [("h", "Key technical risks to manage"), ("ul", risks)]
        queries = [c.issue for c in a.contradictions][:MAX_ITEMS]
        if queries:
            blocks += [("h", "Please raise these with the buyer (pre-bid queries)"), ("ul", queries)]
        if a.questions_for_reviewer:
            blocks += [("h", "Also check"), ("ul", a.questions_for_reviewer[:MAX_ITEMS])]
        if pack_placeholders is not None:
            blocks.append(("p", f"The response pack is attached (technical compliance, compliance form, price sheet, "
                                f"declarations, pre-bid letter, checklist). It has {pack_placeholders} placeholders "
                                f"highlighted in yellow to complete; prices are left blank for BD."))
    elif decision == "No-go":
        blocks.append(("p", f"Not feasible: we will not bid for {ref}."))
        reasons = list(a.fit_reasons[:MAX_ITEMS]) + _risks(a, ("high",))
        if reasons:
            blocks += [("h", "Reasons"), ("ul", reasons)]
    else:
        blocks.append(("p", f"Need clarification before deciding on {ref}."))
        if a.questions_for_reviewer:
            blocks += [("h", "Please find out"), ("ul", a.questions_for_reviewer[:MAX_ITEMS])]

    blocks.append(("p", "Regards,"))
    blocks.append(("p", signature))
    return {"html": _html(blocks), "text": _text(blocks)}


def _html(blocks) -> str:
    out = []
    for kind, value in blocks:
        if kind == "p":
            out.append(f"<p>{escape(value)}</p>")
        elif kind == "h":
            out.append(f"<p><b>{escape(value)}</b></p>")
        else:
            out.append("<ul>" + "".join(f"<li>{escape(v)}</li>" for v in value) + "</ul>")
    return '<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt">' + "\n".join(out) + "</div>"


def _text(blocks) -> str:
    out = []
    for kind, value in blocks:
        out.append("\n".join(f"- {v}" for v in value) if kind == "ul" else str(value))
    return "\n\n".join(out)
