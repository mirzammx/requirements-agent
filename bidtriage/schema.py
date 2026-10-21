"""The structured assessment Claude returns for one bid.

All scalar fields are plain strings; the model writes "not stated" when the bid
does not give a value. Field descriptions are sent to the model as part of the
JSON schema, so they double as instructions.
"""

from typing import Literal

from pydantic import BaseModel, Field

SOURCE = "Where this came from, e.g. 'RFQ_TenderDocument_PSMAHRU.pdf p.9' or 'email body'"


class Spec(BaseModel):
    parameter: str
    value: str
    source: str = Field(description=SOURCE)


class Quantity(BaseModel):
    phase: str = Field(description="e.g. Development, Production year 1")
    item: str
    qty: str
    firm_or_anticipated: Literal["firm", "anticipated", "unclear"]
    source: str = Field(description=SOURCE)


class Risk(BaseModel):
    risk: str
    why_it_matters: str = Field(description="Short engineering or business reason")
    severity: Literal["high", "medium", "low"]
    source: str = Field(description=SOURCE)


class Contradiction(BaseModel):
    issue: str
    source: str = Field(description=SOURCE)


class RedFlag(BaseModel):
    term: str
    implication: str = Field(description="What it means for Rug-Rel; note 'previously accepted' where the profile says so")
    source: str = Field(description=SOURCE)


class Requirement(BaseModel):
    requirement: str
    source: str = Field(description=SOURCE)


class Milestone(BaseModel):
    milestone: str
    when: str
    source: str = Field(description=SOURCE)


class BidAssessment(BaseModel):
    customer: str
    division: str
    rfq_number: str
    title: str
    issue_date: str
    due_date: str
    submission_mode: Literal["GeM", "manual", "e-procurement", "other", "unclear"]
    bid_contact: str
    summary: str = Field(description="Two or three sentences on what is being bought")
    key_specs: list[Spec]
    quantities: list[Quantity]
    technical_risks: list[Risk]
    contradictions: list[Contradiction]
    commercial_red_flags: list[RedFlag]
    eligibility: list[Requirement]
    timeline: list[Milestone]
    fit_verdict: Literal["strong", "possible", "poor", "unclear"]
    fit_reasons: list[str] = Field(description="Reasons tied to the capability profile")
    questions_for_reviewer: list[str]
    documents_read: list[str] = Field(description="Filenames actually used in this assessment")
