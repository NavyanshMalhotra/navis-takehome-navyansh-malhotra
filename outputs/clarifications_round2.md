Subject: Nevis Onboarding - Round 2 Clarifications for Beaconcrest Advisors

Hi Dana,

Thanks again for your prompt and helpful responses to our Round 1 clarifications. That provided significant momentum, and we've successfully mapped a number of entities based on your input.

We've now processed the next batch of data, and have identified a few additional items requiring your expertise to ensure accuracy and complete our data ingestion for Beaconcrest Advisors. Each item below follows the agreed-upon format to make review as efficient as possible.

Please review the following 8 items. For any items you agree with the proposed default, you can simply indicate "Approved as proposed." For those needing adjustment, please provide your preferred option or specific guidance.

---

**1. Unassigned Primary Advisor for Household 'Delgado' (Maria Delgado)**
- **Trigger**: Advisor field is blank in Notion CRM for 'Maria Delgado'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'Maria Delgado'. Status='Legacy'. Service Rep='Marcus Webb'. Page note: 'she doesn't really have a proper advisor of record assigned — should sort that out.'.
- **Candidate Options**:
    (a) Assign to Priya Raman (San Francisco)
    (b) Assign to Marcus Webb (Chicago)
    (c) Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Marcus Webb (Advisor, Chicago)

**2. Unassigned Primary Advisor for Household 'Whitfield' (George Whitfield)**
- **Trigger**: Advisor field is blank in Notion CRM for 'George Whitfield'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'George Whitfield'. Status='Legacy'. Service Rep='A. Novak'. Page note: 'Anna was looking after him before she left the firm — needs reassigning to someone current.'.
- **Candidate Options**:
    (a) Assign to Priya Raman (San Francisco)
    (b) Assign to Marcus Webb (Chicago)
    (c) Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Priya Raman (Senior Advisor, San Francisco)

**3. Unassigned Primary Advisor for Household 'Petit' (Louis Petit)**
- **Trigger**: Advisor field is blank in Notion CRM for 'Louis Petit'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'Louis Petit'. Status='Legacy'. Service Rep='Marcus Webb'. Page note: 'Never got a proper advisor of record assigned.'.
- **Candidate Options**:
    (a) Assign to Priya Raman (San Francisco)
    (b) Assign to Marcus Webb (Chicago)
    (c) Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Marcus Webb (Advisor, Chicago)

**4. Unassigned Primary Advisor for Household 'Vandermeer' (Joris Vandermeer)**
- **Trigger**: Advisor field is blank in Notion CRM for 'Joris Vandermeer'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'Joris Vandermeer'. Status='Active'. Service Rep=''. Page note: 'None'.
- **Candidate Options**:
    (a) Assign to Priya Raman (San Francisco)
    (b) Assign to Marcus Webb (Chicago)
    (c) Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Priya Raman (Senior Advisor, San Francisco)

**5. Unmapped Custodian Account — Carlos Vasquez (CU-5010)**
- **Trigger**: Account 'CU-5010' at Schwab ($980,000.00 USD) has holder 'Carlos Vasquez' with no matching client or household in Notion CRM.
- **Evidence**: Custodian position record in nevis-fde-hometask/sources/custodian_positions.xlsx:Row 12. Custodian=Schwab, Type=Individual.
- **Candidate Options**:
    (a) Add 'Carlos Vasquez' as a new Household and Client in Nevis.
    (b) Link to an existing client under a different legal name/entity.
    (c) Account is closed, winding down, or belongs to another firm.
- **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Vasquez Household'.

**6. Unmapped Custodian Account — Bill Fitzgerald (CU-6023)**
- **Trigger**: Account 'CU-6023' at Schwab ($880,000.00 USD) has holder 'Bill Fitzgerald' with no matching client or household in Notion CRM.
- **Evidence**: Custodian position record in nevis-fde-hometask/sources/custodian_positions.xlsx:Row 35. Custodian=Schwab, Type=Individual.
- **Candidate Options**:
    (a) Add 'Bill Fitzgerald' as a new Household and Client in Nevis.
    (b) Link to an existing client under a different legal name/entity.
    (c) Account is closed, winding down, or belongs to another firm.
- **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Fitzgerald Household'.

**7. Unmapped Custodian Account — Priyanka Mehta (CU-6025)**
- **Trigger**: Account 'CU-6025' at Schwab ($670,000.00 USD) has holder 'Priyanka Mehta' with no matching client or household in Notion CRM.
- **Evidence**: Custodian position record in nevis-fde-hometask/sources/custodian_positions.xlsx:Row 37. Custodian=Schwab, Type=Individual.
- **Candidate Options**:
    (a) Add 'Priyanka Mehta' as a new Household and Client in Nevis.
    (b) Link to an existing client under a different legal name/entity.
    (c) Account is closed, winding down, or belongs to another firm.
- **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Mehta Household'.

**8. Unmatched Interaction — 'Intro Call — Redwood Capital' (Redwood Capital)**
- **Trigger**: Meeting client 'Redwood Capital' cannot be resolved to any existing household in CRM. Canonical Rule 7 forbids minting new households from meetings.
- **Evidence**: Meeting note: 'Referred lead — not in the CRM yet.'. Attendee='James Okafor'. Date='June 8, 2025'.
- **Candidate Options**:
    (a) Lead became an active client under an unlisted name.
    (b) Prospecting lead never converted; archive interaction in prospect lake.
    (c) Typo/alias for an existing household.
- **Proposed Default**: Archive interaction to prospect review queue without minting household pending Dana's confirmation.

---

Please use the following format for your response for quick processing:

1.  **CLARIF-ADV-HH-DELGADO**: [Approved as proposed / Your choice (a/b/c) or specific instruction]
2.  **CLARIF-ADV-HH-WHITFIELD**: [Approved as proposed / Your choice (a/b/c) or specific instruction]
3.  **CLARIF-ADV-HH-PETIT**: [Approved as proposed / Your choice (a/b/c) or specific instruction]
4.  **CLARIF-ADV-HH-VANDERMEER**: [Approved as proposed / Your choice (a/b/c) or specific instruction]
5.  **CLARIF-ACC-CU-5010**: [Approved as proposed / Your choice (a/b/c) or specific instruction]
6.  **CLARIF-ACC-CU-6023**: [Approved as proposed / Your choice (a/b/c) or specific instruction]
7.  **CLARIF-ACC-CU-6025**: [Approved as proposed / Your choice (a/b/c) or specific instruction]
8.  **CLARIF-INT-M-INTRO-CALL-REDWOOD-CAPITAL**: [Approved as proposed / Your choice (a/b/c) or specific instruction]

We appreciate your continued collaboration on these critical items.

Best regards,

[Your Name]
Lead Forward Deployed Engineer
Nevis Onboarding Team