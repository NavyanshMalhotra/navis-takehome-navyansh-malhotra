# Design Note & Slack Rules Lifecycle

## Architecture

Staged multi-agent pipeline on the Google GenAI SDK (`gemini-2.5-flash`, `text-embedding-004`). Each agent is a Python class with a clear responsibility. Deterministic code handles arithmetic, schema validation, FX, and foreign keys. Gemini handles judgment: note mining, entity disambiguation, semantic plausibility, and message drafting.

**Key trade-offs:**

1. **Custom agents vs. framework**: LangChain/CrewAI add abstraction without improving the data wrangling that is the core of this task. Direct SDK gives precise control over prompt schemas, batching, and cost.

2. **Confidence routing**: Entity resolution returns a float confidence. Accounts below `confidence_low_threshold` (0.50) route to clarifications. Above `confidence_high_threshold` (0.85) auto-commit cleanly. This replaces binary orphan/not-orphan logic.

3. **Dual-metric AUM**: Thompson churned but holds $12,400. `market_value_usd = 12400` (custodian truth); `active_aum_usd = 0` (Dana's rule: inactive → excluded from billing). Neither inflates active AUM nor loses reconciliation.

4. **Offline degradation**: Pipeline runs without an API key. LLM steps (note mining, disambiguation, clarification drafting) return conservative defaults. Deterministic resolution still catches most entities.

---

## Slack Business Rules

Rules extracted from `ops_slack_thread.md` via thread-segmented LLM extraction and stored as versioned records in SQLite with 768-dim vector embeddings for deduplication (≥0.90 cosine similarity → update, not duplicate).

| Rule | Dana's Input | Encoding | Correction Mechanism |
|------|-------------|----------|---------------------|
| Legacy status | "Legacy = Harborline book, keep tag" | `Status='Legacy'` → `ACTIVE` + `source_tags: ["acquired from Harborline"]` | Update rule in knowledge store; next sync re-maps |
| Advisor precedence | "Don't guess if blank" | Prioritize Advisor field; forbid Service Rep fallback; route blanks to clarifications | Toggle `allow_service_rep_fallback` flag |
| Anna Novak departed | "A. Novak left, surface her" | Flag any reference to Novak for reassignment via `metadata.departed_staff_names` | Add departure dates to advisor roster |
| AUM = Market Value | "Market value always, ignore cost basis" | Aggregate `Market_Value`; exclude `Cost_Basis` | Decoupled aggregation; can add tax-basis view |
| EUR/CHF conversion | "Convert to USD, note that you did it" | FX at benchmark quarter-end rates; record `currency_original` | Update `config.fx_rates_to_usd` |
| Petrov duplicate | "Known duplicate, collapse them" | Entity resolver detects via `metadata.duplicate_variants` | Remove rule to split on next sync |
| Thompson churned | "Left in 2023, don't count toward AUM" | `status='INACTIVE'`, `active_aum_usd=0.0`, `market_value_usd=12400.0` | Status update to `ACTIVE` restores billing AUM |

**Lifecycle**: Rules are declarative data (not hardcoded logic). HITL resolutions via `POST /api/clarifications/resolve` persist to SQLite and apply automatically on re-sync.
