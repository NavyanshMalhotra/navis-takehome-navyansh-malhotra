Subject: Beaconcrest Onboarding: Round 2 Clarifications

Hi Dana,

Thanks again for your prompt and helpful responses to our first round of clarifications. Your input significantly accelerated our progress.

We've moved forward with implementing those changes and have identified a second, smaller set of items requiring your review. Each item is presented with the context you need to make a quick decision. Please review the options and let us know your preference. If our proposed default aligns with your expectations, simply indicating "Approved as proposed" for that item is sufficient.

---

**1. Unassigned Primary Advisor for Household 'Delgado' (Maria Delgado)**
- **Trigger**: Advisor field is blank in Notion CRM for 'Maria Delgado'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'Maria Delgado'. Status='Legacy'. Service Rep='Marcus Webb'. Page note: 'Marcus has been servicing the account but she doesn't really have a proper advisor of record assigned — should sort that out.'.
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
- **Evidence**: Notion Client row for 'Louis Petit'. Status='Legacy'. Service Rep='Marcus Webb'. Page note: 'None'.
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
- **Trigger**: Account 'CU-5010' at Schwab ($980,000.00 USD) has holder 'Carlos Vasquez' with no matching client or household in Notion CRM. Confidence: 0.20.
- **Evidence**: Custodian record in `nevis-fde-hometask/sources/custodian_positions.xlsx:Row 12`. Custodian=Schwab, Type=Individual. Method=UNMAPPED_ORPHAN_ACCOUNT.
- **Candidate Options**:
    (a) Add 'Carlos Vasquez' as a new Household and Client in Nevis.
    (b) Link to an existing client under a different legal name/entity.
    (c) Account is closed, winding down, or belongs to another firm.
- **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Vasquez Household'.

**6. Unmapped Custodian Account — Priyanka Mehta (CU-6025)**
- **Trigger**: Account 'CU-6025' at Schwab ($670,000.00 USD) has holder 'Priyanka Mehta' with no matching client or household in Notion CRM. Confidence: 0.20.
- **Evidence**: Custodian record in `nevis-fde-hometask/sources/custodian_positions.xlsx:Row 37`. Custodian=Schwab, Type=Individual. Method=UNMAPPED_ORPHAN_ACCOUNT.
- **Candidate Options**:
    (a) Add 'Priyanka Mehta' as a new Household and Client in Nevis.
    (b) Link to an existing client under a different legal name/entity.
    (c) Account is closed, winding down, or belongs to another firm.
- **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Mehta Household'.

**7. Unmatched Interaction — 'Intro Call — Redwood Capital' (Redwood Capital)**
- **Trigger**: Meeting client 'Redwood Capital' cannot be resolved to any existing household in CRM. Canonical Rule 7 forbids minting new households from meetings.
- **Evidence**: Meeting note: 'Referred lead — not in the CRM yet.'. Attendee='James Okafor'. Date='June 8, 2025'.
- **Candidate Options**:
    (a) Lead became an active client under an unlisted name.
    (b) Prospecting lead never converted; archive interaction in prospect lake.
    (c) Typo/alias for an existing household.
- **Proposed Default**: Archive interaction to prospect review queue without minting household pending Dana's confirmation.

---

**Quick Response Template:**

1.  **Delgado**: [Option (a), (b), (c) or Approved as proposed]
2.  **Whitfield**: [Option (a), (b), (c) or Approved as proposed]
3.  **Petit**: [Option (a), (b), (c) or Approved as proposed]
4.  **Vandermeer**: [Option (a), (b), (c) or Approved as proposed]
5.  **Vasquez (CU-5010)**: [Option (a), (b), (c) or Approved as proposed]
6.  **Mehta (CU-6025)**: [Option (a), (b), (c) or Approved as proposed]
7.  **Redwood Capital Interaction**: [Option (a), (b), (c) or Approved as proposed]

Thank you for your continued partnership.

Best regards,

The Nevis Onboarding Team