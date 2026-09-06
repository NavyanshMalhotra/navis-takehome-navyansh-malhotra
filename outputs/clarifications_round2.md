Hi Dana,

Thanks again for the prompt and thorough responses on our Round 1 clarifications. That was incredibly helpful and allowed us to make significant progress.

We've now consolidated the remaining open items for your review in what we're calling "Round 2 Clarifications." As before, each item is structured to be easily scannable and answerable, outlining the issue, supporting evidence, candidate solutions, and our proposed default action.

Please let us know if our proposed defaults work for you, or if you'd like to select a different option for any of these items.

---

### Round 2 Clarifications

*   **Unassigned Primary Advisor for Household 'Delgado' (Maria Delgado)**
    *   **Trigger**: Advisor field is blank in Notion CRM for 'Maria Delgado'. Canonical Rule 1 requires exactly one non-null primary advisor.
    *   **Evidence**: Notion Client row for 'Maria Delgado'. Status='Legacy'. Service Rep='Marcus Webb'. Page note: 'Marcus has been servicing the account but she doesn't really have a proper advisor of record assigned — should sort that out.'
    *   **Candidate Options**:
        (a) Assign to Priya Raman (San Francisco)
        (b) Assign to Marcus Webb (Chicago)
        (c) Assign to Elena Sokolova (Chicago)
    *   **Proposed Default**: Assign to Marcus Webb (Advisor, Chicago)

*   **Unassigned Primary Advisor for Household 'Whitfield' (George Whitfield)**
    *   **Trigger**: Advisor field is blank in Notion CRM for 'George Whitfield'. Canonical Rule 1 requires exactly one non-null primary advisor.
    *   **Evidence**: Notion Client row for 'George Whitfield'. Status='Legacy'. Service Rep='A. Novak'. Page note: 'Anna was looking after him before she left the firm — needs reassigning to someone current.'
    *   **Candidate Options**:
        (a) Assign to Priya Raman (San Francisco)
        (b) Assign to Marcus Webb (Chicago)
        (c) Assign to Elena Sokolova (Chicago)
    *   **Proposed Default**: Assign to Priya Raman (Senior Advisor, San Francisco)

*   **Unassigned Primary Advisor for Household 'Petit' (Louis Petit)**
    *   **Trigger**: Advisor field is blank in Notion CRM for 'Louis Petit'. Canonical Rule 1 requires exactly one non-null primary advisor.
    *   **Evidence**: Notion Client row for 'Louis Petit'. Status='Legacy'. Service Rep='Marcus Webb'. Page note: 'Never got a proper advisor of record assigned.'
    *   **Candidate Options**:
        (a) Assign to Priya Raman (San Francisco)
        (b) Assign to Marcus Webb (Chicago)
        (c) Assign to Elena Sokolova (Chicago)
    *   **Proposed Default**: Assign to Marcus Webb (Advisor, Chicago)

*   **Unassigned Primary Advisor for Household 'Vandermeer' (Joris Vandermeer)**
    *   **Trigger**: Advisor field is blank in Notion CRM for 'Joris Vandermeer'. Canonical Rule 1 requires exactly one non-null primary advisor.
    *   **Evidence**: Notion Client row for 'Joris Vandermeer'. Status='Active'. Service Rep=''. Page note: 'None'.
    *   **Candidate Options**:
        (a) Assign to Priya Raman (San Francisco)
        (b) Assign to Marcus Webb (Chicago)
        (c) Assign to Elena Sokolova (Chicago)
    *   **Proposed Default**: Assign to Priya Raman (Senior Advisor, San Francisco)

*   **Unmapped Custodian Account — Carlos Vasquez (CU-5010)**
    *   **Trigger**: Account 'CU-5010' at Schwab ($980,000.00 USD) has holder 'Carlos Vasquez' with no matching client or household in Notion CRM. Resolution confidence: 0.20.
    *   **Evidence**: Custodian position record in nevis-fde-hometask/sources/custodian_positions.xlsx:Row 12. Custodian=Schwab, Type=Individual. Method=UNMAPPED_ORPHAN_ACCOUNT.
    *   **Candidate Options**:
        (a) Add 'Carlos Vasquez' as a new Household and Client in Nevis.
        (b) Link to an existing client under a different legal name/entity.
        (c) Account is closed, winding down, or belongs to another firm.
    *   **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Vasquez Household'.

*   **Unmapped Custodian Account — Priyanka Mehta (CU-6025)**
    *   **Trigger**: Account 'CU-6025' at Schwab ($670,000.00 USD) has holder 'Priyanka Mehta' with no matching client or household in Notion CRM. Resolution confidence: 0.20.
    *   **Evidence**: Custodian position record in nevis-fde-hometask/sources/custodian_positions.xlsx:Row 37. Custodian=Schwab, Type=Individual. Method=UNMAPPED_ORPHAN_ACCOUNT.
    *   **Candidate Options**:
        (a) Add 'Priyanka Mehta' as a new Household and Client in Nevis.
        (b) Link to an existing client under a different legal name/entity.
        (c) Account is closed, winding down, or belongs to another firm.
    *   **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Mehta Household'.

*   **Unmatched Interaction — 'Intro Call — Redwood Capital' (Redwood Capital)**
    *   **Trigger**: Meeting client 'Redwood Capital' cannot be resolved to any existing household in CRM. Canonical Rule 7 forbids minting new households from meetings.
    *   **Evidence**: Meeting note: 'Referred lead — not in the CRM yet.'. Attendee='James Okafor'. Date='June 8, 2025'.
    *   **Candidate Options**:
        (a) Lead became an active client under an unlisted name.
        (b) Prospecting lead never converted; archive interaction in prospect lake.
        (c) Typo/alias for an existing household.
    *   **Proposed Default**: Archive interaction to prospect review queue without minting household pending Dana's confirmation.

---

Please use the following format for your response if you need to make any adjustments:

*   **CLARIF-ADV-HH-DELGADO**: Option (b)
*   **CLARIF-ADV-HH-WHITFIELD**: Option (a)
*   **CLARIF-ADV-HH-PETIT**: Option (b)
*   **CLARIF-ADV-HH-VANDERMEER**: Option (a)
*   **CLARIF-ACC-CU-5010**: Option (a) - Please create new household 'Vasquez Household'
*   **CLARIF-ACC-CU-6025**: Option (a) - Please create new household 'Mehta Household'
*   **CLARIF-INT-M-INTRO-CALL-REDWOOD-CAPITAL**: Option (b)

If all proposed defaults are acceptable, a simple "Approved as proposed" will suffice.

Thanks,
Nevis Onboarding Team