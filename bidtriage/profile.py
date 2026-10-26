"""Rug-Rel company facts from prompts/company_profile.toml. Empty means unknown."""

import tomllib
from pathlib import Path

PROFILE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "company_profile.toml"

# key -> human label used in [[placeholders]]
PROFILE_LABELS = {
    "company_name": "Company name",
    "address": "Company address",
    "phone": "Phone",
    "email": "Email",
    "website": "Website",
    "gstin": "GSTIN",
    "pan": "PAN",
    "udyam_number": "Udyam registration no.",
    "msme_category": "MSE category (Micro/Small/Medium)",
    "social_category": "Social category",
    "women_owned": "Women-owned (Yes/No)",
    "authorised_signatory": "Authorised signatory name",
    "signatory_designation": "Signatory designation",
    "local_content_percent": "Local content %",
    "value_addition_location": "Location of local value addition",
    "iso_9001": "ISO 9001 certificate",
    "as9100": "AS9100 certificate",
    "cemilac_approvals": "CEMILAC approvals held",
    "buyer_vendor_codes": "Buyer vendor registration code",
    "bank_details": "Bank details",
}
PROFILE_KEYS = list(PROFILE_LABELS)


def load_profile(path: Path | str | None = None) -> dict[str, str]:
    path = Path(path) if path else PROFILE_PATH
    data = tomllib.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    profile = {key: str(data.get(key, "")).strip() for key in PROFILE_KEYS}
    return profile | {k: str(v).strip() for k, v in data.items() if k not in profile}


def fact(profile: dict[str, str], key: str) -> str:
    """The profile value, or a [[placeholder]] naming what is missing."""
    return profile.get(key) or f"[[{PROFILE_LABELS.get(key, key)}]]"
