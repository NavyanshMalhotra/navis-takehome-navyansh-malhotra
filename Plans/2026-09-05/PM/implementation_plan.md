# Architectural Audit & Pitfall Analysis: Nevis FDE Agentic Platform
**Date**: 2026-09-05 (PM)  
**Cross-Reference**: `Nevis - Forward Deployed Engineer Home Task.pdf` & `Nevis - Canonical Data Model.pdf`

---

## 1. Task Evaluation Criteria & Alignment Matrix

| Evaluation Dimension | What the Evaluator Specifically Looks For | How Our Design Flawlessly Addresses It |
| :--- | :--- | :--- |
| **Core Deliverable (Running Code)** | *"Code we can run that ingests the sources, does the mapping, and produces the two outputs... A rough script that runs and reasons well beats a beautiful one that doesn't run."* | CLI entry point `python run_pipeline.py` runs end-to-end in **one command** with zero friction. The FastAPI and Web UI are built on top of the exact same core pipeline modules. |
| **Agentic Balance (Where LLM Earns Its Place)** | *"Not one giant do-everything prompt, and not a pure rule engine either: show where the model earns its place and where deterministic code is the better tool."* | **Deterministic**: File parsing, schema checks, exact joins, AUM sums, FX multiplication, referential FK validation.<br>**LLM Agentic**: Page note fact mining, entity resolution (trusts, joint, LLCs, nicknames), confidence scoring, and drafting scoped Round 2 clarification questions. |
| **Knowledge Layer** | *"When a stakeholder answer resolves an ambiguity... it is captured and reapplied automatically, for this client, and ideally reusable across future clients. Build it, don't just describe it."* | Declarative Knowledge Engine (`knowledge_base.py` / `rules.json`) capturing Dana's Slack answers as parameterized rules (e.g. `AcquisitionLineageRule`, `AdvisorPrecedenceRule`, `CurrencyHandlingRule`, `DeduplicationRule`). |
| **Provenance Traceability** | *"Provenance: each output value traceable to a rule, a model call, or a human answer."* | Field-level provenance dictionaries attached to every canonical record citing exact file, line/row, agent/rule ID, raw input value, and confidence. |
| **Post-Mapping Validation** | *"Post-mapping validation that catches plausible-but-wrong results."* | Adversarial validator checking all 7 Nevis Canonical Rules (AUM null vs zero, orphan accounts/meetings, foreign currency normalization, non-null advisor constraint). |
| **Customer-Facing Clarifications (Round 2)** | *"The next message back to Dana... Scoped, answerable question, not a shrug: what triggered it, the evidence, candidate options, and your proposed default. Must not re-ask anything round 1 settled."* | Pre-computed, professional Slack message formatted with exact triggers, evidence, options (a/b/c), and proposed defaults for every unresolved item. |
| **Evaluator Reproducibility** | *"Commit the outputs your run produced... A mock fallback for reproducibility is fine, but the real LLM path must be implemented and demonstrably used."* | Real Google Gemini API / OpenAI LLM integration via environment variables (`GEMINI_API_KEY`), backed by an automatic deterministic mock fallback so evaluators can run the entire test suite even without an API key. |

---

## 2. Critical Pitfalls & Mitigation Strategies

### Pitfall 1: Over-Engineering the Presentation Layer at the Expense of the CLI Core
*   **The Trap**: Building a complex frontend/cloud setup that obscures or breaks the simple command-line execution (`python run_pipeline.py`) required by the rubric.
*   **The Mitigation**: The system architecture is built **CLI-First**. The standalone script `run_pipeline.py` executes the entire pipeline, generates `outputs/canonical_output.json` and `outputs/clarifications_round2.md`, and runs all validation tests. The FastAPI server and Web UI directly import the pipeline runner, providing a visual inspection layer without altering core execution.

### Pitfall 2: Re-Asking Settled Round 1 Slack Questions
*   **The Trap**: Asking Dana questions she already answered in `sources/ops_slack_thread.md`.
*   **The Mitigation**: Our knowledge layer explicitly encodes Dana's answers:
    1.  `Status = Legacy`: Treated as `ACTIVE`, mapped with `source_tags: ["acquired from Harborline"]`.
    2.  `Advisor` vs `Service Rep`: Only `Advisor` owns the relationship. If blank, never guess from `Service Rep`.
    3.  `A. Novak`: Left the firm; any client pointing to her must be surfaced for reassignment.
    4.  `Cost Basis` vs `Market Value`: Use `Market Value` only for AUM; ignore `Cost Basis`.
    5.  `Yusuf Al-Rashid`: EUR currency converted to USD using quarter-end FX rate; record original currency.
    6.  `Dmitri Petrov`: Known duplicate; collapsed into single client and household.
    7.  `Thompson Household`: Left in 2023; status set to `INACTIVE`, AUM set to `null` (or 0 active AUM).
    *Zero of these questions appear in Round 2.*

### Pitfall 3: Missing the Second Non-USD Account (`Francesca Bianchi` in CHF)
*   **The Trap**: Handling Yusuf Al-Rashid's EUR account because Dana mentioned it, but failing to notice `CU-6022` (`Francesca Bianchi`) which is held in **CHF** (Swiss Francs at Pictet in Geneva) with 2,100,000 CHF.
*   **The Mitigation**: Canonical Rule 5 is implemented as a **universal currency conversion engine**, not a hardcoded EUR rule. It detects any non-USD currency code, fetches the corresponding quarter-end FX rate (EUR: 1.071, CHF: 1.114), computes `market_value_usd`, preserves `currency_original = "CHF"`, and documents the conversion in provenance.

### Pitfall 4: Canonical Rule 1 Conflict (Mandatory Non-Null Primary Advisor)
*   **The Trap**: Canonical Rule 1 says *"One primary advisor per household. Required and non-null."* However, 4 clients have blank advisors in Notion (`Maria Delgado`, `George Whitfield`, `Louis Petit`, `Joris Vandermeer`). Dana explicitly commanded: *"Don't guess. Flag those to me and I'll tell you the right advisor."*
*   **The Mitigation**: If we insert `primary_advisor_id: null` into the canonical book, we violate Rule 1. If we guess an advisor, we violate Dana's rule. 
    *Resolution*: These 4 households are staged in the **Pending Client Clarification** registry and routed directly to Dana in Round 2 with proposed advisor assignments based on client segment and office. They are excluded from the finalized committed book until Dana confirms, preventing dirty/invalid records from entering production.

### Pitfall 5: Canonical Rule 3 (Unknown != Zero)
*   **The Trap**: Defaulting missing account balances to `$0.00` for prospects (`Susan Fairbanks`, `Miguel Costa`, `Klaus Bauer`) or clients with no accounts (`Diego Vargas`, `Amara Nwosu`).
*   **The Mitigation**: Canonical Rule 3 strictly dictates that a household with no known accounts has AUM `null`, not `0`. The aggregation engine explicitly sets `household.market_value_usd = None` if no accounts roll up to that household.

### Pitfall 6: Canonical Rule 4 & 7 (No Orphan Accounts or Interactions)
*   **The Trap**: Leaving orphan accounts (`Carlos Vasquez`, `Priyanka Mehta`) or orphan meetings (`Redwood Capital`) silently dropped or forced into artificial households.
*   **The Mitigation**:
    *   `Carlos Vasquez` (`CU-5010`) and `Priyanka Mehta` (`CU-6025`) are routed to `clarifications_round2.md` with candidate options (e.g. unentered CRM client, alternate legal name, account transferred out).
    *   `Redwood Capital` is flagged as an orphan interaction because Rule 7 explicitly forbids minting a new household from an interaction.

### Pitfall 7: Shrugging Instead of Scoped, Answerable Questions
*   **The Trap**: Writing vague clarification questions like *"Please advise on Carlos Vasquez."*
*   **The Mitigation**: Every clarification in Round 2 follows the strict 4-part schema:
    1.  **Trigger**: Exactly what data condition caused the flag.
    2.  **Evidence**: Custodian account number, custodian name, balance, notes.
    3.  **Candidate Options**: Concrete (a), (b), (c) choices.
    4.  **Proposed Default**: What Nevis will do if Dana simply replies "Approve defaults".

---

## 3. Detailed Data Inventory & Mapping Master Table

| Entity / Source Record | Key Challenges & Data Quirks | Classification & Resolution | Output Destination |
| :--- | :--- | :--- | :--- |
| **Robert Chen & Linda Chen** | Listed on separate CRM rows; Linda's household is blank in CSV; note says "Wife of Robert Chen — same household". | Joined into `Chen Household`. Robert = `PRIMARY`, Linda = `SPOUSE`. Joint account `CU-5001` mapped to household. | `canonical_output.json` |
| **Ada Okonkwo Revocable Trust** (`CU-5003`) | Legal trust entity name at Fidelity. | Resolved to natural person `Ada Okonkwo` in `Okonkwo` Household. Account type: `TRUST`. | `canonical_output.json` |
| **Nakamura Holdings LLC** (`CU-5006`) & **Nakamura, Kenji** (`CU-5011`) | Corporate LLC entity and inverted personal name. Meeting note discusses Kenji's IRA vs LLC. | Both accounts mapped to `Nakamura` Household (`Kenji Nakamura`). Corporate account typed as `CORPORATE`. | `canonical_output.json` |
| **G. Whitfield** (`CU-5005`) | Initial + surname at Pershing. Notion has `George Whitfield`. | Resolved to `George Whitfield`. Advisor is blank and Service Rep is `A. Novak` (departed). | Flagged to Dana for advisor reassignment. |
| **Bill Fitzgerald** (`CU-6023`) | Diminutive "Bill" vs CRM "William Fitzgerald". | Resolved via nickname engine to `William Fitzgerald` in `Fitzgerald` Household. | `canonical_output.json` |
| **Yusuf Al-Rashid** (`CU-5008`) | Held in EUR at Lombard Intl. | Converted EUR -> USD at 1.071 rate. Original currency preserved as `EUR`. | `canonical_output.json` |
| **Francesca Bianchi** (`CU-6022`) | Held in CHF at Pictet in Geneva. | Converted CHF -> USD at 1.114 rate. Original currency preserved as `CHF`. | `canonical_output.json` |
| **Dmitri Petrov** & **Petrov, Dmitri** | Duplicate CRM records with slight spelling & inverted name. | Collapsed into single client and household per Dana's Slack resolution. | `canonical_output.json` |
| **Thompson Household** (`CU-5009`) | Churned client; account winding down. | Status = `INACTIVE`. AUM = `null`. Tagged with departure lineage. | `canonical_output.json` |
| **Carlos Vasquez** (`CU-5010`) | Schwab account ($980k) with no CRM record. | Orphan account. Blocked from canonical output per Rule 4. | `clarifications_round2.md` |
| **Priyanka Mehta** (`CU-6025`) | Schwab account ($670k) with no CRM record. | Orphan account. Blocked from canonical output per Rule 4. | `clarifications_round2.md` |
| **Redwood Capital** (Meeting) | Prospect meeting with lead not yet in CRM. | Orphan interaction. Blocked from canonical output per Rule 7. | `clarifications_round2.md` |
| **Maria Delgado**, **Louis Petit**, **Joris Vandermeer** | Missing advisor; Dana forbade guessing from Service Rep. | Rule 1 requires non-null advisor. | `clarifications_round2.md` |

---

## 4. Pipeline Execution Sequence

```
Step 1: Ingestion & Pre-flight Validation
  ├── Validate schemas (Notion CSVs, Meetings, Custodian XLSX, Advisor Roster)
  ├── Verify existence of all linked Markdown pages
  └── Emit Data Sanity Report

Step 2: Knowledge Layer Initialization
  ├── Load Slack Round 1 extracted rules
  └── Load cross-client reusable business rules

Step 3: Document & Context Mining (Agentic)
  ├── Extract familial relations from client Markdown notes (e.g. Linda Chen)
  └── Extract meeting context and attendance details

Step 4: Entity Resolution & Household Synthesis (Agentic + Heuristics)
  ├── Normalize names (inversions, initials, diminutives)
  ├── Parse legal entities (Trusts, LLCs, Joint WROS)
  ├── Link accounts to households
  └── Compute match confidence scores

Step 5: Canonical Transformation & Normalization
  ├── Apply FX conversions (EUR, CHF -> USD)
  ├── Normalize enums (Account types, Interaction types, Roles)
  ├── Roll up household AUM (preserving null for zero accounts)
  └── Attach detailed field-level provenance

Step 6: Adversarial Validation
  ├── Assert 7 Nevis Canonical Rules
  └── Segregate records: High Confidence -> Canonical, Low/Mid/Blocked -> Clarifications

Step 7: Artifact Generation
  ├── Write outputs/canonical_output.json
  ├── Write outputs/clarifications_round2.md
  ├── Write DESIGN.md
  └── Serve via FastAPI & Web Dashboard (optional inspection)
```
