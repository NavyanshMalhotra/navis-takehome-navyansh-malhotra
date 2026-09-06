# Design Note & Slack Rules Lifecycle

## Architecture

Coordinated multi-agent swarm built on **Google ADK (`google-adk` 2.8.0)** and the **Google GenAI SDK** (`gemini-2.5-flash`, `text-embedding-004`) with **OpenTelemetry** distributed tracing. Each agent inherits from `google.adk.agents.BaseAgent` with distinct domain responsibilities. Deterministic code handles arithmetic, schema validation, FX conversions, and foreign key integrity. Google GenAI handles contextual judgment: unstructured note mining, legal entity disambiguation, semantic plausibility audits, and clarification drafting.

**Key Architectural Decisions:**

1. **Google ADK Agent Swarm**: Agents operate as modular nodes (`KnowledgeMiningAgent`, `DossierMinerAgent`, `EntityResolverAgent`, `CanonicalTransformerAgent`, `AuditorReflectionAgent`, `ClarificationAgent`) coordinated by `NevisSwarmOrchestrator`. Each stage emits OpenTelemetry spans capturing latency, model calls, tool executions, and errors.

2. **Reflective Feedback Loop**: The auditor agent (`AuditorReflectionAgent`) does not simply fail on violations; it evaluates candidate anomalies and orchestrates reflective re-routing of unmapped accounts and interactions before final artifact generation.

3. **Confidence Routing**: The entity resolver assigns continuous confidence scores. Records below `confidence_low_threshold` (0.50) route to Round 2 clarifications for human operator triage. Records with high confidence (≥0.85) commit cleanly into the canonical schema.

4. **Collision-Proof Household Synthesis**: Distinct clients sharing surnames without explicit family links are disambiguated with client-scoped identifiers, preventing unwanted merging of unrelated households.

5. **Dual-Metric AUM**: Accounts retain custodian balance truth (`market_value_usd = 12400.0`), while household billing metrics enforce institutional rules: inactive/churned households have `active_aum_usd = 0.0`. Reconciliation and billing accuracy are preserved simultaneously.

6. **Offline Robustness**: When running without an API key, the swarm leverages deterministic fallbacks (including an onomastic diminutive dictionary for standard nicknames like Bill $\rightarrow$ William) to maintain pipeline execution.

---

## Slack Business Rules Lifecycle

Institutional rules are extracted from `ops_slack_thread.md` via thread-segmented LLM extraction and persisted in SQLite with 768-dimensional vector embeddings for semantic retrieval and cosine deduplication (≥0.90 similarity updates existing rules).

| Rule | Dana's Clarification | Encoding & Canonical Application | Lifecycle & Correction Mechanism |
|------|----------------------|-----------------------------------|----------------------------------|
| Legacy Status | "Legacy = Harborline book, keep tag" | `Status='Legacy'` $\rightarrow$ `ACTIVE` + `source_tags: ["acquired from Harborline"]` | Update rule in SQLite knowledge store; re-sync applies new mapping |
| Advisor Precedence | "Don't guess if blank" | Prioritize Advisor column; forbid Service Rep guessing; route blanks to clarifications | Configurable `allow_service_rep_fallback` policy |
| Departed Staff | "A. Novak left, surface her" | Flag references to departed staff via rule metadata `departed_staff_names` | Update departed staff roster in knowledge layer |
| AUM = Market Value | "Market value always, ignore cost basis" | Aggregate custodian `Market_Value`; exclude `Cost_Basis` | Decoupled aggregation logic |
| Foreign Currency | "Convert to USD, note that you did it" | FX conversion at benchmark quarter-end rates; record `currency_original` | Update rates in `config.fx_rates_to_usd` |
| Entity Deduplication | "Known duplicate, collapse them" | Dynamic deduplication via `metadata.duplicate_variants` | Remove rule to split entities on next sync |
| Churned Clients | "Left in 2023, don't count toward AUM" | `status='INACTIVE'`, `active_aum_usd=0.0`, `market_value_usd=12400.0` | Setting status to `ACTIVE` restores billing AUM |

**Runtime Governance**: Human-in-the-loop (HITL) resolutions submitted via `POST /api/clarifications/resolve` persist as versioned `KnowledgeRule` records in SQLite, ensuring decisions survive restarts and automatically re-apply on future syncs.
