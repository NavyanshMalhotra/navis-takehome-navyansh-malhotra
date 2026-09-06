# Design Note: ReAct Multi-Agent Architecture & Slack Rules Lifecycle

## 1. System Architecture & Key Trade-Offs

The Nevis onboarding engine bridges messy RIA data reality (Notion exports, custodian spreadsheets, and Slack institutional lore) with the strict relational constraints of the Nevis canonical model.

```
                           ┌───────────────────────────────────────────────┐
                           │      Lead Orchestrator Agent (ReAct Graph)    │
                           └───────┬───────────────────────────────▲───────┘
                                   │ Coordinates blackboard state  │
                                   ▼                               │
┌──────────────────────────────────┴───────────────────────────────┴───────────────────────────────────┐
│                                 INTER-AGENT COMMUNICATION BUS                                        │
│                                                                                                      │
│  ┌───────────────────────┐          ┌──────────────────────┐          ┌───────────────────────────┐  │
│  │ KnowledgeAgent        │◄────────►│ DocMinerAgent        │◄────────►│ EntityResolverAgent       │  │
│  │ Ingests & vector-     │ (policy) │ Mines Notion notes   │ (roles / │ Disambiguates accounts,   │  │
│  │ embeds Slack lore     │          │ for family / roles   │  spouses)│ trusts, LLCs to households│  │
│  └──────────┬────────────┘          └──────────┬───────────┘          └─────────────┬─────────────┘  │
│             │                                  │                                    │                │
│             └──────────────────────────────────┼────────────────────────────────────┘                │
│                                                ▼                                                     │
│                                     ┌─────────────────────┐                                          │
│                                     │ MappingAgent        │                                          │
│                                     │ Transforms book &   │                                          │
│                                     │ computes Active AUM │                                          │
│                                     └──────────┬──────────┘                                          │
│                                                │                                                     │
│                                                ▼                                                     │
│                                     ┌─────────────────────┐                                          │
│                                     │ AuditorAgent        │──┐ (Reflective Re-eval Feedback Loop)    │
│                                     │ Rules 1-8 + Semantic│  │                                       │
│                                     │ Plausibility Checks │◄─┘                                       │
│                                     └──────────┬──────────┘                                          │
│                                                │                                                     │
│                                                ▼                                                     │
│                                     ┌─────────────────────┐                                          │
│                                     │ ClarificationAgent  │                                          │
│                                     │ Drafts Round 2 msg  │                                          │
│                                     └─────────────────────┘                                          │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Architectural Decisions & Trade-Offs:
1. **ReAct Multi-Agent Graph vs. Chained LLMs vs. Pure Heuristics**:
   - *Trade-off*: Pure heuristic regex fails on real-world wealth management nuances (spousal links, corporate signers, trust variants). Monolithic prompts or rigid sequential LLM chains are brittle and cannot self-correct.
   - *Decision*: We built a ReAct agent graph with dedicated agents (`KnowledgeAgent`, `DocMinerAgent`, `EntityResolverAgent`, `MappingAgent`, `AuditorAgent`, `ClarificationAgent`). Deterministic code handles arithmetic, schema validation, FX multiplication, and foreign keys. Gemini (`gemini-2.5-flash`) handles judgment: unstructured note mining, ambiguous entity resolution, semantic plausibility, and message drafting. Agents communicate via tools and can trigger reflective feedback cycles before escalating.
2. **Strict Canonical Gating vs. Silent Guessing**:
   - *Trade-off*: Canonical Rule 1 mandates non-null primary advisors. Four clients (`Delgado`, `Whitfield`, `Petit`, `Vandermeer`) had blank advisors in Notion.
   - *Decision*: Per Dana's explicit instruction (*"Don't guess. Flag those to me"*), we route unassigned accounts to Clarifications Round 2 with proposed defaults, assigning provisional staging status rather than inventing fake data.
3. **Dual-Metric Accounting: Total Market Value vs. Active Billing AUM**:
   - *Trade-off*: Thompson churned in 2023 but holds a remaining account balance ($12,400). Dropping the account loses reconciliation with custodian truth; counting it inflates active AUM.
   - *Decision*: We implement dual-metric accounting on `Household`: `market_value_usd = $12,400` (custodian truth) and `active_aum_usd = $0.00` (enforcing Dana's rule: `is_active = False` $\rightarrow$ active AUM = 0).
4. **Unified Google Encoding & Model Stack**:
   - *Decision*: A single `GEMINI_API_KEY` powers both generation (`gemini-2.5-flash`) and vector embeddings via Google's `text-embedding-004` encoding endpoint, requiring zero secondary provider keys.
5. **Storage Architecture: Local SQLite Cache vs. Cloud DB (GCloud)**:
   - *Local CLI Execution*: Caches extracted rules and 768-dim vector embeddings in a lightweight local SQLite database (`outputs/knowledge_store.db`), ensuring fast, reproducible execution without re-embedding on every run.
   - *Production Cloud Architecture (GCloud)*: For firm-wide RIA deployments, the persistence layer targets Cloud SQL (PostgreSQL with `pgvector`) or Vertex AI Vector Search / Firestore on Google Cloud. This allows institutional rules and entity aliases to be shared across advisors, persisted across sync loops, and queried via cosine similarity.

---

## 2. Slack Business Rules: Scalable Extraction, Encoding, & Lifecycle Management

### Thread-Segmented Incremental Extraction Architecture
In enterprise RIA environments, Slack channels contain thousands of messages across months. Passing an entire raw transcript in a single monolithic prompt is fundamentally unscalable (exceeding token budgets, burning latency/cost, causing lost-in-the-middle omissions, and preventing incremental updates).

`KnowledgeEngine` implements a **Thread-Segmented Incremental Extraction Architecture**:
1. **Conversational Thread Segmentation**: Parses raw channel transcripts into atomic thematic exchanges/threads (`_segment_slack_transcript`) based on conversational question-answer turns.
2. **Incremental Extraction**: Each thread is processed independently via Gemini with `prompts/slack_rule_extraction.txt`, extracting atomic rules with exact message-level citations (`sources/ops_slack_thread.md#THREAD-X`).
3. **Semantic Vector Indexing & Deduplication**: Rules are encoded into 768-dim embeddings via Google's `text-embedding-004`. The engine queries the local SQLite vector database (`KnowledgeStoreDB`) using cosine similarity. If an equivalent rule already exists ($\ge 0.90$ similarity), metadata is updated rather than inserting duplicate records.
4. **Production Webhook Integration**: This design natively supports live Slack webhooks, ingesting incoming threads as atomic deltas without re-reading historical transcripts.

### Elimination of Static Maps & Dictionaries
All static lookup dictionaries (such as `NICKNAME_MAP` and manual month translation tables) were completely eliminated:
- **Dynamic Onomastic Reasoning**: `EntityResolverAgent` uses live Gemini onomastic reasoning (`is_diminutive_or_alias`) backed by an in-memory session cache to evaluate whether informal names (`Bob`, `Bill`) map to legal names (`Robert`, `William`), cross-referenced with aliases extracted from Notion CRM dossiers.
- **Declarative Rule Metadata**: Departed staff lists (`departed_staff_names`) and duplicate entities (`duplicate_variants`) are extracted dynamically into `KnowledgeRule.metadata` rather than hardcoded in procedural Python functions.

| Rule ID | Dana's Input (Slack Thread) | Pipeline Encoding & Automated Next Sync | How It Gets Corrected If Stale |
| :--- | :--- | :--- | :--- |
| `RULE_LEGACY_IS_HARBORLINE_ACTIVE` | *"Legacy = Harborline book acquired in 2019... keep tag."* | Maps `Status='Legacy'` $\rightarrow$ `ACTIVE`; injects `source_tags: ["acquired from Harborline"]`. | Parameterized in `KnowledgeEngine`. Changing the rule updates downstream mapping automatically on next sync. |
| `RULE_ADVISOR_PRECEDENCE` | *"Advisor owns relationship... Don't guess if blank."* | Prioritizes `Advisor`. Forbids fallback to junior `Service Rep`; routes unassigned clients to Clarifications. | Flag `allow_service_rep_fallback: False`. If firm policy changes, toggling to `True` reassigns automatically. |
| `RULE_DEPARTED_STAFF_ANNA_NOVAK` | *"A. Novak is Anna Novak, contractor who left... surface her."* | Flags any service rep or attendee pointing to `Novak` for high-priority reassignment via `metadata.departed_staff_names`. | Advisor roster departure registry. Adding departure dates to advisors triggers reassignment flags automatically. |
| `RULE_AUM_MARKET_VALUE_ONLY` | *"Market value always, as of quarter-end. Ignore cost basis."* | Aggregates custodian `Market_Value`; excludes `Cost_Basis` from AUM calculations. | Decoupled aggregation engine. Can calculate tax-basis or billing-AUM via separate view models. |
| `RULE_FOREIGN_CURRENCY_USD_REPORTING` | *"Convert EUR to USD for totals... note that you did it."* | Multi-currency engine converts EUR/CHF to USD at benchmark quarter-end FX; records `currency_original`. | Central FX rate table (`config.fx_rates_to_usd`). Updating rate table updates valuations automatically. |
| `RULE_DEDUPLICATE_DMITRI_PETROV` | *"Petrov is a known duplicate... collapse them."* | Entity resolver detects inverted variations via `metadata.duplicate_variants` and collapses records. | Stored in knowledge base. If client confirms two distinct individuals share a name, removing rule splits them on next sync. |
| `RULE_CHURNED_CLIENT_THOMPSON_AUM_EXCLUSION` | *"Thompson left in 2023... shouldn't count toward active AUM."* | Sets `status='INACTIVE'`, `is_active=False`, `market_value_usd=12400.0`, and `active_aum_usd=0.0`. | Status rule. If Thompson re-engages, status update to `ACTIVE` restores active billing AUM immediately. |

### Rule Lifecycle & Operator Feedback:
- **Declarative Rule Registry**: Rules are stored as versioned, declarative data structures (`KnowledgeRule`), not hardcoded procedural logic.
- **Delta-Sync Invalidation**: When an operator resolves an ambiguity via the API or dashboard (`POST /api/clarifications/resolve`), the override is timestamped, persisted in the knowledge store, and triggers an incremental delta-sync that re-validates canonical constraints.

