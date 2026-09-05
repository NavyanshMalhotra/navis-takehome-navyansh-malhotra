# Design Note & Slack Rules Architecture

## 1. Shape of the System & Architectural Trade-Offs

The Nevis onboarding engine bridges unstructured RIA reality (messy Notion exports, custodian spreadsheets, and Slack institutional lore) and the strict relational constraints of the Nevis canonical model.

```
Ingestion & Validation ──► Knowledge Layer ──► MoE Agent Network ──► Adversarial Auditor ──► Canonical JSON & Round 2 Slack
 (CSV, XLSX, Notes)       (Slack Encoded)     (Entity / Doc Miner)   (7 Canonical Rules)      (Committed Book + Questions)
```

### Key Trade-Offs Made:
1. **Deterministic Foundations vs. LLM Judgment**:
   - *Trade-off*: We avoided both extreme antipatterns: a giant monolithic prompt (brittle, non-deterministic, unscalable) and a pure regex rule engine (fails on real-world edge cases like spousal notes, trust variants, and nicknames).
   - *Decision*: Deterministic Python handles schema validation, mathematical aggregations, FX multiplication, exact ID lookups, and foreign key enforcement. The LLM (Google Gemini / Strands pattern) is deployed surgically where it earns its place: extracting implied family structures from unstructured Markdown notes, disambiguating complex legal entity grantors (`Ada Okonkwo Revocable Trust`), resolving diminutives (`Bob` -> `Robert`), and generating empathic, scoped questions for Dana.
2. **Strict Canonical Gating vs. Silent Defaulting**:
   - *Trade-off*: Canonical Rule 1 mandates non-null primary advisors. Four clients (`Delgado`, `Whitfield`, `Petit`, `Vandermeer`) had blank advisors in Notion.
   - *Decision*: Dana explicitly ordered: *"Don't guess. Flag those to me."* Rather than inventing fake advisors or defaulting to departed staff (`A. Novak`), we segregated unassigned households into a **Pending Clarification** staging state, allowing the valid book to achieve 100% canonical compliance while presenting Dana with a scoped, single-click resolution batch.
3. **Field-Level Provenance Overhead vs. Auditability**:
   - *Trade-off*: Attaching `_provenance` metadata to every mapped attribute increases JSON payload size (~275 KB).
   - *Decision*: In wealth management, unexplained data mutation is fatal. Provenance citing the source file, row, agent method, and confidence is mandatory for regulatory auditability and client trust.

---

## 2. Slack Business Rules: Extraction, Encoding, & Lifecycle Management

From `sources/ops_slack_thread.md`, we extracted and codified 7 foundational business rules into our declarative `KnowledgeEngine`:

| Rule ID | Dana's Input (Slack Thread) | Pipeline Encoding & Next-Sync Automation | How It Gets Corrected If Wrong / Stale |
| :--- | :--- | :--- | :--- |
| `RULE_LEGACY_IS_HARBORLINE_ACTIVE` | *"Legacy = Harborline book acquired in 2019. Active clients... keep tag."* | Maps `Status='Legacy'` -> `ACTIVE`; injects `source_tags: ["acquired from Harborline"]`. | Parameterized in `KnowledgeEngine`. If Harborline terms change, updating the rule updates all downstream views on the next sync. |
| `RULE_ADVISOR_VS_SERVICE_REP` | *"Advisor owns relationship. Service Rep is junior/ops... Don't guess if blank."* | Checks `Advisor` column first. If blank, explicitly forbids fallback to `Service Rep`; routes to Clarifications. | Configurable flag `allow_service_rep_fallback: False`. If firm policy changes, toggling to `True` reassigns automatically. |
| `RULE_DEPARTED_STAFF_NOVAK` | *"A. Novak is Anna Novak, contractor who left... surface anything pointing to her."* | Scans `Service Rep` and meeting attendee fields for `Novak`; triggers priority reassignment flags. | Staff roster registry. Adding a departure date flag to an advisor automatically triggers reassignment sweeps. |
| `RULE_AUM_MARKET_VALUE_ONLY` | *"Market value always, as of quarter-end. Ignore cost basis."* | Aggregates `Market_Value` only; excludes `Cost_Basis` from canonical AUM calculations. | Decoupled aggregation engine. Can compute both tax-basis and billing-AUM via distinct view models. |
| `RULE_FOREIGN_CURRENCY_USD` | *"Convert EUR to USD for totals... note that you did it."* | Generalized multi-currency engine converting EUR/CHF to USD at quarter-end FX rates; preserves `currency_original`. | Central FX rate table (`config.fx_rates_to_usd`). Updating rate table updates valuations automatically. |
| `RULE_DEDUPLICATE_PETROV` | *"Petrov is a known duplicate... collapse them."* | Entity resolver detects phonetic and inverted variations (`Dmitri Petrov` vs `Petrov, Dmitri`) and unifies records. | Stored in `entity_aliases.json`. If client confirms two people share a name, removing the alias splits them on next sync. |
| `RULE_CHURNED_THOMPSON` | *"Thompson left in 2023... Mark inactive, shouldn't count toward active AUM."* | Sets `status='INACTIVE'`; excludes from active AUM rollups while retaining history. | Status rule. If Thompson re-engages, status update to `ACTIVE` restores active book reporting immediately. |

### Rule Lifecycle & Stale Rule Mitigation:
- **Declarative Rule Registry**: Rules are stored as versioned, declarative data structures (`KnowledgeRule`), not hardcoded procedural code.
- **Delta-Sync Invalidation**: When an operator or client modifies an assumption in the UI or via API (`POST /api/clarifications/resolve`), the override is timestamped, persisted, and immediately triggers an incremental delta-sync that re-validates canonical constraints.
