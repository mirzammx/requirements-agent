"""Code-enforced rules on a ResponseDraft, applied whatever the model returned.

1. Text is cleaned of control characters (PDF page breaks etc.) that Word/Excel reject.
2. A clause needing a decision always carries a [[placeholder]].
3. Nothing claims a certification or registration the company profile does not record.
"""

import re

from bidtriage.draft_schema import ResponseDraft

# pattern in the clause text -> (name shown to the reviewer, profile key that backs it)
CERT_RULES = [
    (re.compile(r"\bAS[\s\-]?9100", re.I), "AS9100", "as9100"),
    (re.compile(r"\bISO[\s\-]?9001", re.I), "ISO 9001", "iso_9001"),
    (re.compile(r"\bCEMILAC\b", re.I), "CEMILAC approval", "cemilac_approvals"),
    (re.compile(r"\bUdyam\b|\bUdyog\s+Aadhaa?r\b|\bNSIC\b|\bMSEs?\b|\bMSMEs?\b", re.I),
     "MSE/Udyam registration", "udyam_number"),
    (re.compile(r"vendor\s+registration|registered\s+(?:vendor|supplier)|"
                r"registered\s+with\s+(?:HAL|BEL|DRDO|BDL|BEML|ISRO|the\s+(?:buyer|purchaser|division))", re.I),
     "buyer vendor registration", "buyer_vendor_codes"),
]
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
HAS_PLACEHOLDER = re.compile(r"\[\[.*?\]\]", re.S)
# Statuses that assert something about Rug-Rel and so must be backed by the profile.
ASSERTING = ("complied", "noted")


def _missing_certs(text: str, profile: dict[str, str]) -> list[str]:
    return [name for pattern, name, key in CERT_RULES if pattern.search(text) and not profile.get(key)]


def _confirm(missing: list[str]) -> str:
    return f"[[CONFIRM: Rug-Rel {', '.join(missing)} not in company profile]]"


def _clean(value):
    if isinstance(value, str):
        return CONTROL_CHARS.sub("", value)
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def apply_guards(draft: ResponseDraft, profile: dict[str, str]) -> ResponseDraft:
    draft = ResponseDraft.model_validate(_clean(draft.model_dump()))
    for section in draft.sections:
        for clause in section.clauses:
            if clause.status in ASSERTING:
                missing = _missing_certs(f"{clause.requirement} {clause.response}", profile)
                if missing:
                    clause.status = "review"
                    clause.response = f"{_confirm(missing)} {clause.response}".strip()
            if clause.status in ("review", "deviation") and not HAS_PLACEHOLDER.search(clause.response):
                clause.response = f"[[{clause.status.upper()}: {clause.response or clause.requirement}]]"
    for row in draft.compliance_form_rows:
        missing = _missing_certs(f"{row.term} {row.response}", profile)
        if missing and _confirm(missing) not in row.response:
            row.response = f"{row.response} {_confirm(missing)}".strip()
    return draft
