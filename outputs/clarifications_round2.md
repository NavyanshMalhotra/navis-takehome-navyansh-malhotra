# Slack Message — #nevis-onboarding (Round 2 Clarifications)

> **To**: Dana Ruiz (Head of Operations, Beaconcrest Advisors)  
> **From**: Alex / Nevis Onboarding Team  
> **Subject**: Round 2 Disambiguation Shortlist — Final Items for Canonical Mapping  

Hi Dana — huge thanks again for the clarifications in Round 1! We encoded all your answers into our system: the Harborline 'Legacy' lineage is preserved as active clients, Market Value is locked in as the sole AUM benchmark, Yusuf's EUR account is converted to USD, Dmitri Petrov's duplicate is collapsed, and the Thompson household is marked inactive.

We've now run our automated pipeline across your entire book. Out of your full book, **over 90% mapped cleanly and automatically** into the Nevis canonical model.

Below is the exact **shortlist of items Round 1 didn't settle** where we need your judgment rather than guessing. To make this as fast as possible for you, each item includes the background, candidate options, and a **proposed default**. You can simply reply approving the defaults or specify any adjustments in a couple of lines!

---

## Part 1: Primary Advisor Assignments (Blank in CRM)
Per our Round 1 discussion, we do not guess or fall back to Service Reps. The following 4 clients have a blank Advisor field in Notion:

### Item 1: Unassigned Primary Advisor for Household 'Delgado' (Maria Delgado)
- **Trigger**: Advisor field is blank in Notion CRM for 'Maria Delgado'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'Maria Delgado'. Status='Legacy'. Service Rep='Marcus Webb'. Page note: 'Unassigned advisor of record'.
- **Candidate Options**:
  - Assign to Priya Raman (San Francisco)
  - Assign to Marcus Webb (Chicago)
  - Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Marcus Webb (Advisor, Chicago)

### Item 2: Unassigned Primary Advisor for Household 'Whitfield' (George Whitfield)
- **Trigger**: Advisor field is blank in Notion CRM for 'George Whitfield'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'George Whitfield'. Status='Legacy'. Service Rep='A. Novak'. Page note: 'None'. WARNING: Service Rep 'A. Novak' is Anna Novak who departed the firm.
- **Candidate Options**:
  - Assign to Priya Raman (San Francisco)
  - Assign to Marcus Webb (Chicago)
  - Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Priya Raman (Senior Advisor, San Francisco)

### Item 3: Unassigned Primary Advisor for Household 'Petit' (Louis Petit)
- **Trigger**: Advisor field is blank in Notion CRM for 'Louis Petit'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'Louis Petit'. Status='Legacy'. Service Rep='Marcus Webb'. Page note: 'Unassigned advisor of record'.
- **Candidate Options**:
  - Assign to Priya Raman (San Francisco)
  - Assign to Marcus Webb (Chicago)
  - Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Marcus Webb (Advisor, Chicago)

### Item 4: Unassigned Primary Advisor for Household 'Vandermeer' (Joris Vandermeer)
- **Trigger**: Advisor field is blank in Notion CRM for 'Joris Vandermeer'. Canonical Rule 1 requires exactly one non-null primary advisor.
- **Evidence**: Notion Client row for 'Joris Vandermeer'. Status='Active'. Service Rep=''. Page note: 'None'.
- **Candidate Options**:
  - Assign to Priya Raman (San Francisco)
  - Assign to Marcus Webb (Chicago)
  - Assign to Elena Sokolova (Chicago)
- **Proposed Default**: Assign to Priya Raman (Senior Advisor, San Francisco)

## Part 2: Custodian Accounts with No Matching CRM Client
Our custodian positions file contains 2 active investment accounts where the account holder name does not exist anywhere in your Notion CRM:

### Item 5: Unmapped Custodian Account — Carlos Vasquez (CU-5010)
- **Trigger**: Account 'CU-5010' at Schwab ($980,000.00 USD) has holder 'Carlos Vasquez' with no matching client or household in Notion CRM.
- **Evidence**: Custodian position record in /Users/navyansh/Desktop/Development/Nevis take home/navis-takehome-navyansh-malhotra/nevis-fde-hometask/sources/custodian_positions.xlsx:Row 12. Custodian=Schwab, Type=Individual.
- **Candidate Options**:
  - Add 'Carlos Vasquez' as a new Household and Client in Nevis.
  - Link to an existing client under a different legal name/entity.
  - Account is closed, winding down, or belongs to another firm.
- **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Vasquez Household'.

### Item 6: Unmapped Custodian Account — Priyanka Mehta (CU-6025)
- **Trigger**: Account 'CU-6025' at Schwab ($670,000.00 USD) has holder 'Priyanka Mehta' with no matching client or household in Notion CRM.
- **Evidence**: Custodian position record in /Users/navyansh/Desktop/Development/Nevis take home/navis-takehome-navyansh-malhotra/nevis-fde-hometask/sources/custodian_positions.xlsx:Row 37. Custodian=Schwab, Type=Individual.
- **Candidate Options**:
  - Add 'Priyanka Mehta' as a new Household and Client in Nevis.
  - Link to an existing client under a different legal name/entity.
  - Account is closed, winding down, or belongs to another firm.
- **Proposed Default**: Stage account under holding queue; request Dana confirm client identity or create Household 'Mehta Household'.

## Part 3: Meeting Interaction with Unregistered Lead
We identified 1 meeting in your Notion calendar with an organization that does not exist in your client database:

### Item 7: Unmatched Interaction — 'Intro Call — Redwood Capital' (Redwood Capital)
- **Trigger**: Meeting client 'Redwood Capital' cannot be resolved to any existing household in CRM. Canonical Rule 7 forbids minting new households from meetings.
- **Evidence**: Meeting note: 'Referred lead — not in the CRM yet'. Attendee='James Okafor'. Date='June 8, 2025'.
- **Candidate Options**:
  - Lead became an active client under an unlisted name.
  - Prospecting lead never converted; archive interaction in prospect lake.
  - Typo/alias for an existing household.
- **Proposed Default**: Archive interaction to prospect review queue without minting household pending Dana's confirmation.

---

### How to Reply (Quick-Response Template)
If the proposed defaults look good to you, you can literally reply with:
```text
Approved all proposed defaults as listed.
```
Or if you want to tweak specific assignments:
```text
1. Delgado: Assign to Marcus Webb
2. Whitfield: Assign to Priya Raman
3. Petit: Assign to Marcus Webb
4. Vandermeer: Assign to Elena Sokolova
5. Vasquez: New client, assign to Priya Raman
6. Mehta: New client, assign to Grace Bennett
7. Redwood: Archive as prospecting lead
```

Once you reply, our pipeline will apply your answers instantly and lock in the final book!

Best,
Alex & The Nevis Onboarding Team