Hi Dana,

Thanks for the swift and clear responses to our first round of clarifications! That was extremely helpful and allowed us to make significant progress on the initial data ingestion.

As we continue with the next phase of data reconciliation and mapping, we've identified a few more items that require your expert input to ensure everything is accurately represented in Nevis. Our aim here is to ensure all data is accurately represented, reflecting Beaconcrest's operational reality.

Each item below outlines the specific issue, the evidence we've found, candidate options for resolution, and our proposed default if no further input is provided.

---

### Round 2 Clarifications

**1. CLARIF-ADV-HH-DELGADO: Unassigned Primary Advisor for Household 'Delgado' (Maria Delgado)**
- **Trigger**: Advisor field is blank in Notion CRM for 'Maria Delgado'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'Maria Delgado'. Status='Legacy'. Service Rep='Marcus Webb'. Page note: 'doesn't really have a proper advisor of record assigned'.
- **Candidate Options**:
    (a) Assign to Priya Raman (San Francisco)
    (b) Assign to Marcus Webb (Chicago)
    (c) Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Marcus Webb (Advisor, Chicago)

**2. CLARIF-ADV-HH-WHITFIELD: Unassigned Primary Advisor for Household 'Whitfield' (George Whitfield)**
- **Trigger**: Advisor field is blank in Notion CRM for 'George Whitfield'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'George Whitfield'. Status='Legacy'. Service Rep='A. Novak'. Page note: 'Anna was looking after him before she left the firm — needs reassigning to someone current.'. WARNING: Service Rep 'A. Novak' is Anna Novak who departed the firm.
- **Candidate Options**:
    (a) Assign to Priya Raman (San Francisco)
    (b) Assign to Marcus Webb (Chicago)
    (c) Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Priya Raman (Senior Advisor, San Francisco)

**3. CLARIF-ADV-HH-PETIT: Unassigned Primary Advisor for Household 'Petit' (Louis Petit)**
- **Trigger**: Advisor field is blank in Notion CRM for 'Louis Petit'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'Louis Petit'. Status='Legacy'. Service Rep='Marcus Webb'. Page note: 'Never got a proper advisor of record assigned.'.
- **Candidate Options**:
    (a) Assign to Priya Raman (San Francisco)
    (b) Assign to Marcus Webb (Chicago)
    (c) Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Marcus Webb (Advisor, Chicago)

**4. CLARIF-ADV-HH-VANDERMEER: Unassigned Primary Advisor for Household 'Vandermeer' (Joris Vandermeer)**
- **Trigger**: Advisor field is blank in Notion CRM for 'Joris Vandermeer'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'Joris Vandermeer'. Status='Active'. Service Rep=''. Page note: 'None'.
- **Candidate Options**:
    (a) Assign to Priya Raman (San Francisco)
    (b) Assign to Marcus Webb (Chicago)
    (c) Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Priya Raman (Senior Advisor, San Francisco)

**5. CLARIF-ACC-CU-5010: Unmapped Custodian Account — Carlos Vasquez (CU-5010)**
- **Trigger**: Account 'CU-5010' at Schwab ($980,000.00 USD) has holder 'Carlos Vasquez' with no matching client or household in Notion CRM.
- **Evidence**: Custodian position record in `nevis-fde-hometask/sources/custodian_positions.xlsx:Row 12`. Custodian=Schwab, Type=Individual.
- **Candidate Options**:
    (a) Add 'Carlos Vasquez' as a new Household and Client in Nevis.
    (b) Link to an existing client under a different legal name/entity.
    (c) Account is closed, winding down, or belongs to another firm.
- **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Vasquez Household'.

**6. CLARIF-ACC-CU-6023: Unmapped Custodian Account — Bill Fitzgerald (CU-6023)**
- **Trigger**: Account 'CU-6023' at Schwab ($880,000.00 USD) has holder 'Bill Fitzgerald' with no matching client or household in Notion CRM.
- **Evidence**: Custodian position record in `nevis-fde-hometask/sources/custodian_positions.xlsx:Row 35`. Custodian=Schwab, Type=Individual.
- **Candidate Options**:
    (a) Add 'Bill Fitzgerald' as a new Household and Client in Nevis.
    (b) Link to an existing client under a different legal name/entity.
    (c) Account is closed, winding down, or belongs to another firm.
- **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Fitzgerald Household'.

**7. CLARIF-ACC-CU-6025: Unmapped Custodian Account — Priyanka Mehta (CU-6025)**
- **Trigger**: Account 'CU-6025' at Schwab ($670,000.00 USD) has holder 'Priyanka Mehta' with no matching client or household in Notion CRM.
- **Evidence**: Custodian position record in `nevis-fde-hometask/sources/custodian_positions.xlsx:Row 37`. Custodian=Schwab, Type=Individual.
- **Candidate Options**:
    (a) Add 'Priyanka Mehta' as a new Household and Client in Nevis.
    (b) Link to an existing client under a different legal name/entity.
    (c) Account is closed, winding down, or belongs to another firm.
- **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Mehta Household'.

**8. CLARIF-INT-M-INTRO-CALL-REDWOOD-CAPITAL: Unmatched Interaction — 'Intro Call — Redwood Capital' (Redwood Capital)**
- **Trigger**: Meeting client 'Redwood Capital' cannot be resolved to any existing household in CRM. Canonical Rule 7 forbids minting new households from meetings.
- **Evidence**: Meeting note: 'Referred lead — not in the CRM yet.'. Attendee='James Okafor'. Date='June 8, 2025'.
- **Candidate Options**:
    (a) Lead became an active client under an unlisted name.
    (b) Prospecting lead never converted; archive interaction in prospect lake.
    (c) Typo/alias for an existing household.
- **Proposed Default**: Archive interaction to prospect review queue without minting household pending Dana's confirmation.

---

Please let us know if the proposed defaults work for you, or if you'd like to select an alternative. You can simply reply with "Approved as proposed" for all, or specify any changes by item ID:

```
[Your Response]
Approved as proposed.
OR
CLARIF-ADV-HH-DELGADO: Option (a)
CLARIF-ACC-CU-5010: Option (c)
... etc.
```

Happy to jump on a quick call if any of these warrant a deeper dive.

Best regards,

[Your Name]
Lead Forward Deployed Engineer
Nevis Onboarding Team