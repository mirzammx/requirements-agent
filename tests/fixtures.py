from bidtriage.schema import (
    BidAssessment,
    Contradiction,
    Milestone,
    Quantity,
    RedFlag,
    Requirement,
    Risk,
    Spec,
)

RFQ = "RFQ_TenderDocument_PSMAHRU.pdf"


def sample_assessment() -> BidAssessment:
    return BidAssessment(
        customer="Hindustan Aeronautics Limited",
        division="Avionics Division, Hyderabad",
        rfq_number="HAL/HYD/IMM-INDG/M1/PSM-AHRU/2026/01",
        title="Design and Development of AHRU Power Supply Module",
        issue_date="2026-09-16",
        due_date="2026-10-13",
        submission_mode="manual",
        bid_contact="Rajeev Kumar Jain, DGM (Indigenisation)",
        summary="Indigenous 28 V DC-input multi-rail power supply module for the AHRU, plus a test jig.",
        key_specs=[Spec(parameter="Input voltage", value="28 ±1 V DC", source=f"{RFQ} p.9")],
        quantities=[Quantity(phase="Development", item="ESS units", qty="4",
                             firm_or_anticipated="firm", source=f"{RFQ} p.16")],
        technical_risks=[Risk(risk="100 ms hold-up", why_it_matters="~4.5 J storage in 30 mm height",
                              severity="high", source=f"{RFQ} p.9")],
        contradictions=[Contradiction(issue="Overload table lists 3 VPEL rail not in output list",
                                      source=f"{RFQ} p.9")],
        commercial_red_flags=[RedFlag(term="IPR rests with HAL", implication="Source code and Gerbers handed over",
                                      source=f"{RFQ} p.5")],
        eligibility=[Requirement(requirement="Local content >= 50%", source=f"{RFQ} p.30")],
        timeline=[Milestone(milestone="PDR", when="T0+6 months", source=f"{RFQ} p.17")],
        fit_verdict="possible",
        fit_reasons=["28 V DC input and 3U form factor match SBU-2 custom supplies"],
        questions_for_reviewer=["Due date 13 Oct has passed: ask BD whether an extension was granted."],
        documents_read=[RFQ, "PSM_AHRU_PriceBid.pdf"],
    )
