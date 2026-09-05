# Architecture & Implementation Plan: Nevis FDE Agentic Data Pipeline

## 1. Problem Context & Goal
Nevis requires onboarding a new wealth management client (Beaconcrest Advisors) whose data is spread across messy sources:
1. **Notion CRM Export**: `Clients*.csv` + client markdown pages with unstructured notes.
2. **Notion Meetings Export**: `Meetings*.csv` + meeting markdown pages with unstructured notes.
3. **Custodian Account Positions**: `custodian_positions.xlsx` containing investment accounts, multi-currency balances, and cost basis.
4. **Advisor Roster**: `advisor_roster.csv` with official advisor IDs, names, and roles.
5. **Slack Onboarding Thread (Round 1)**: Operational rules answered by Dana Ruiz (Head of Ops).

The goal is to build an end-to-end, runnable Python **agentic data mapping pipeline** that:
- Combines deterministic wrangling, structured business rules, and LLM reasoning for high-judgment tasks.
- Produces **canonical_output** with full provenance and **clarifications_round2** (customer-ready questions for Dana).
- Adheres to Nevis canonical schema rules and handles edge cases systematically.

---

## 2. Key Insights & Edge Case Mapping

| Category | Finding / Anomaly in Data | Resolution Strategy |
| :--- | :--- | :--- |
| **Household & Client Roles** | `Linda Chen` is listed separately without household ID in CSV, but markdown note says "Wife of Robert Chen — same household". | LLM/rule extracts relation from markdown note -> group into `Chen Household`, Robert Chen as `PRIMARY`, Linda Chen as `SPOUSE`. |
| **Duplicate Clients** | `Dmitri Petrov` and `Petrov, Dmitri` exist in CRM. | Slack Round 1 rule: collapse into single client & household. |
| **Advisor Assignment** | Multiple clients have blank `Advisor` (e.g. `Maria Delgado`, `George Whitfield`, `Louis Petit`, `Joris Vandermeer`). | Slack Round 1 rule: Never guess from Service Rep. Anna Novak left. Flag unassigned advisors to Dana in Round 2 clarifications. |
| **Foreign Currency** | `CU-5008` (Yusuf Al-Rashid) is in `EUR`; `CU-6022` (Francesca Bianchi) is in `CHF` (Pictet in Geneva). | Convert both to USD using 2025-06-30 quarter-end FX rates; record `currency_original` and provenance. |
| **Orphan Accounts** | `Carlos Vasquez` (`CU-5010`) and `Priyanka Mehta` (`CU-6025`) exist at custodian but have no CRM client record. | Canonical Rule 4 forbids orphan accounts in canonical output -> route to Round 2 clarifications for Dana. |
| **Orphan Interactions** | `Intro Call — Redwood Capital` has client "Redwood Capital" (lead not in CRM yet). | Canonical Rule 7 forbids orphan interactions and minting new households from meetings -> flag to Dana. |
| **Alias Resolution** | Meeting with `Bob Chen` -> `Robert Chen`; Account `Ada Okonkwo Revocable Trust` -> `Ada Okonkwo`; `Bill Fitzgerald` -> `William Fitzgerald`. | LLM entity resolution / fuzzy matching with high confidence auto-applied. |
| **AUM Rollup & Null vs Zero** | Prospects (`Susan Fairbanks`, `Miguel Costa`, `Klaus Bauer`) and clients with no accounts (`Diego Vargas`, `Amara Nwosu`). | Canonical Rule 3: AUM is `null`, not `0.0`. |

---

## 3. Pipeline Architecture

```
sources/
 ├── notion_export/
 ├── custodian_positions.xlsx
 ├── advisor_roster.csv
 └── ops_slack_thread.md
         │
         ▼
┌────────────────────────────────────────────────────────┐
│ 1. Ingestion & Preprocessing Layer                     │
│    - Parse CSV, XLSX, Markdown page bodies             │
│    - Clean raw text, dates, names, currency symbols    │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ 2. Knowledge & Rules Engine (Extensible)               │
│    - Slack Round 1 Knowledge Base (Dana's rules)       │
│    - Cross-client reusable canonical business rules   │
│    - Fast deterministic matcher (exact matches, etc.) │
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ 3. Agentic LLM Reasoning Layer                         │
│    - Markdown notes unstructured fact extraction       │
│    - Entity resolution (Trusts, nicknames, LLCs)       │
│    - Enum normalization & confidence scoring (0-1)    │
│    - Decision router: confident (>0.85) vs flag (<0.85)│
└───────────────────────┬────────────────────────────────┘
                        │
                        ▼
┌────────────────────────────────────────────────────────┐
│ 4. Post-Mapping Integrity Validator                    │
│    - Enforce 7 Nevis Canonical Rules                  │
│    - FK referential integrity (Households, Advisors)   │
│    - Zero vs Null AUM verification                     │
│    - Provenance attachment (Rule / Model / Human)     │
└───────────────────────┬────────────────────────────────┘
                        │
         ┌──────────────┴──────────────┐
         ▼                             ▼
┌──────────────────────┐     ┌──────────────────────┐
│  canonical_output    │     │ clarifications       │
│  (JSON / structured) │     │ (Round 2 for Dana)   │
└──────────────────────┘     └──────────────────────┘
```

---

## 4. Proposed Decisions & Open Questions for User Review

### Decision 1: LLM Provider & Execution Mode
- **Proposed Approach**: Support **Google Gemini API** (`gemini-2.5-flash` / `gemini-1.5-flash` using `google-genai` / `google.generativeai` or `GEMINI_API_KEY`) with an automatic, zero-dependency offline mock / rule-based fallback so anyone grading the task can run it with 1 single command immediately, with or without an API key.
- *Advise on*: Any preference on default model or provider configuration?

### Decision 2: Output Format for `canonical_output`
- **Proposed Approach**: Produce a unified `canonical_output.json` containing the 5 entity lists (`households`, `clients`, `accounts`, `advisors`, `interactions`), each entity bearing an explicit `_provenance` metadata block detailing the exact source rule / LLM step / human Slack resolution.
- *Advise on*: Confirm if single JSON or multiple entity files is preferred.

### Decision 3: FX Rates for Non-USD Accounts
- Yusuf Al-Rashid (`CU-5008`: 1,875,000 EUR) and Francesca Bianchi (`CU-6022`: 2,100,000 CHF).
- **Proposed Approach**: Use standard 2025-06-30 quarter-end FX rates (EUR/USD: 1.071, CHF/USD: 1.114) and record both `market_value_usd` and `currency_original`.

### Decision 4: Handling Records Requiring Dana's Approval
- For records with unassigned advisors (`Delgado`, `Whitfield`, `Petit`, `Vandermeer`), orphan accounts (`Vasquez`, `Mehta`), and orphan meetings (`Redwood Capital`):
- **Proposed Approach**: Route to `clarifications.md` formatted specifically as Round 2 Slack questions for Dana Ruiz (trigger, evidence, candidate options, proposed default).
