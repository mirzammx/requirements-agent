from bidtriage.draft_schema import (
    ClauseResponse,
    ComplianceSection,
    FormRow,
    PreBidQuery,
    PriceLine,
    RequiredDocument,
    ResponseDraft,
)

RFQ = "RFQ_TenderDocument_PSMAHRU.pdf"


def sample_draft() -> ResponseDraft:
    return ResponseDraft(
        rfq_number="HAL/HYD/IMM-INDG/M1/PSM-AHRU/2026/01",
        title="Design and Development of AHRU Power Supply Module",
        buyer_name="Hindustan Aeronautics Limited, Avionics Division",
        buyer_address="Balanagar, Hyderabad 500042",
        buyer_contact="Rajeev Kumar Jain, DGM (Indigenisation), rajeev.jain@hal-india.co.in",
        due_date="2026-10-13",
        offer_validity_date="2027-10-13",
        sections=[
            ComplianceSection(heading="Part-B: Project Requirements", clauses=[
                ClauseResponse(ref="4.3", requirement="Comply with IMAP 2023 & IMTAR-21 Ver 2.0",
                               status="complied", response="Complied", source=f"{RFQ} p.2"),
                ClauseResponse(ref="Annex-1 Sl.7", requirement="Hold up time 100 msec", status="review",
                               response="[[REVIEW: 100 ms at 45 W in 30 mm height; confirm or propose deviation]]",
                               source=f"{RFQ} p.9"),
            ]),
        ],
        compliance_form_title="Compliance Statement for Development of Power Supply Module of AHRU",
        compliance_form_rows=[
            FormRow(sno="1", term="Offer validity 365 days from due date (indicate date)",
                    response="Y. Valid till 2027-10-13"),
            FormRow(sno="4", term="Minimum Local Content (MLC): indicate percentage",
                    response="Y. [[MLC %]]"),
        ],
        price_schedule_title="Price Bid: Power Supply Module of AHRU",
        price_lines=[
            PriceLine(phase="Design Phase (DP)", sno="1", description="Design and Development Cost incl. QT and prototype unit", qty="1"),
            PriceLine(phase="Design Phase (DP)", sno="2", description="Indigenised PSM (ESS Units)", qty="4"),
            PriceLine(phase="Production Phase (PP)", sno="1", description="Indigenised PSM (1st Year)", qty="10"),
        ],
        required_documents=[
            RequiredDocument(document="Technical bid in sealed envelope", notes="Superscribe RFQ no. and due date",
                             source=f"{RFQ} p.24"),
            RequiredDocument(document="Udyam registration certificate", notes="If MSE", source=f"{RFQ} p.26"),
        ],
        prebid_queries=[
            PreBidQuery(clause_ref="Annex-1 Sl.20 vs 8.1(d)",
                        query="Please confirm whether MIL-STD-461E or 461C Part 2 Class A1b applies.",
                        source=f"{RFQ} p.9, 11"),
        ],
        declarations_needed=["mlc", "land_border"],
    )
