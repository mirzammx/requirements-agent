"""Code-enforced rules on a ResponseDraft, applied whatever the model returned.

1. A clause needing a decision always carries a [[placeholder]].
2. Nothing claims a certification or registration the company profile does not record.
"""

import re

from bidtriage.draft_schema import ResponseDraft

# pattern in the clause text -> (name shown to the reviewer, profile key that backs it)
CERT_RULES = [
    (re.compile(r"\bAS\s?9100", re.I), "AS9100", "as9100"),
    (re.compile(r"\bISO\s?9001", re.I), "ISO 9001", "iso_9001"),
    (re.compile(r"\bCEMILAC\b", re.I), "CEMILAC approval", "cemilac_approvals"),
    (re.compile(r"\bUdyam\b|\bMSEs?\b|\bMSMEs?\b", re.I), "MSE/Udyam registration", "udyam_number"),
    (re.compile(r"vendor\s+registration|registered\s+with\s+HAL", re.I), "buyer vendor registration",
     "buyer_vendor_codes"),
]


def _missing_certs(text: str, profile: dict[str, str]) -> list[str]:
    return [name for pattern, name, key in CERT_RULES if pattern.search(text) and not profile.get(key)]


def _confirm(missing: list[str]) -> str:
    return f"[[CONFIRM: Rug-Rel {', '.join(missing)} not in company profile]]"


def apply_guards(draft: ResponseDraft, profile: dict[str, str]) -> ResponseDraft:
    draft = draft.model_copy(deep=True)
    for section in draft.sections:
        for clause in section.clauses:
            if clause.status == "complied":
                missing = _missing_certs(clause.requirement, profile)
                if missing:
                    clause.status = "review"
                    clause.response = f"{_confirm(missing)} {clause.response}".strip()
            if clause.status in ("review", "deviation") and "[[" not in clause.response:
                clause.response = f"[[{clause.status.upper()}: {clause.response or clause.requirement}]]"
    for row in draft.compliance_form_rows:
        missing = _missing_certs(row.term, profile)
        if missing and "[[" not in row.response:
            row.response = f"{row.response} {_confirm(missing)}".strip()
    return draft
