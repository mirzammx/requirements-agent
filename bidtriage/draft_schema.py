"""Structured draft of a bid response, returned by the model and rendered by code.

There is deliberately no price field anywhere: prices are always left to BD.
Field descriptions are sent to the model as part of the JSON schema.
"""

from typing import Literal

from pydantic import BaseModel, Field

PLACEHOLDER = "Use [[...]] for anything a person must decide or supply, e.g. [[REVIEW: ...]] or [[MLC %]]"
SOURCE = "Where this came from, e.g. 'RFQ_TenderDocument_PSMAHRU.pdf p.9'"


class ClauseResponse(BaseModel):
    ref: str = Field(description="The RFQ's own numbering, e.g. '7.2' or 'Annexure-1 Sl.7'")
    requirement: str = Field(description="The clause, condensed to its obligation in one or two sentences")
    status: Literal["complied", "review", "deviation", "noted", "not_applicable"] = Field(
        description="complied: standard and acceptable; review: a person must decide; deviation: we propose "
                    "different terms; noted: informational; not_applicable")
    response: str = Field(description=f"Text for the 'Rug-Rel Compliance' column. {PLACEHOLDER}")
    source: str = Field(description=SOURCE)


class ComplianceSection(BaseModel):
    heading: str = Field(description="RFQ section heading, e.g. 'Part-B: Project Requirements'")
    clauses: list[ClauseResponse]


class FormRow(BaseModel):
    sno: str
    term: str = Field(description="The buyer form's row text")
    response: str = Field(description=f"Y/N plus any required detail. {PLACEHOLDER}")


class PriceLine(BaseModel):
    phase: str = Field(description="Group heading from the buyer's price schedule, e.g. 'Design Phase (DP)'")
    sno: str
    description: str
    qty: str = Field(description="Quantity exactly as in the schedule, digits only where possible")


class RequiredDocument(BaseModel):
    document: str
    notes: str = Field(description="Format, signing, envelope or other instructions")
    source: str = Field(description=SOURCE)


class PreBidQuery(BaseModel):
    clause_ref: str
    query: str = Field(description="A polite, specific clarification question to the buyer")
    source: str = Field(description=SOURCE)


class ResponseDraft(BaseModel):
    rfq_number: str
    title: str
    buyer_name: str
    buyer_address: str
    buyer_contact: str
    due_date: str
    offer_validity_date: str = Field(description="Due date plus the RFQ's validity period, or [[...]] if unknown")
    sections: list[ComplianceSection] = Field(description="Every clause of the RFQ in its own order")
    compliance_form_title: str = Field(description="Title of the buyer's compliance form, or '' if none")
    compliance_form_rows: list[FormRow] = Field(description="Rows of the buyer's compliance form; empty if none")
    price_schedule_title: str
    price_lines: list[PriceLine] = Field(description="Lines of the buyer's price schedule; never any prices")
    required_documents: list[RequiredDocument]
    prebid_queries: list[PreBidQuery]
    declarations_needed: list[Literal["mlc", "land_border", "mse"]]
