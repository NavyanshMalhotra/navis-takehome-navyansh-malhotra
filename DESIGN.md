# Nevis FDE Technical Design Specification

## 1. Executive Summary & Framework Selection

The Nevis Agentic Data Onboarding Pipeline transforms heterogeneous RIA books of record (Notion CRM exports, custodian XLSX positions, advisor rosters, and Slack communications) into the Nevis canonical wealth data model.

* **Agent Framework**: **Google Agent Development Kit (`google-adk` 2.8.0)** using the official **Google GenAI SDK** (`gemini-2.5-flash` + `text-embedding-004`).
* **Why Google ADK**: Purpose-built for multi-agent systems with explicit agent lifecycles, typed tool contracts, and native OpenTelemetry integration. Avoids the abstraction bloat and hidden control flow of LangChain or AutoGen.
* **Why Multi-Agent Swarm (vs. Monolithic Prompt)**: Financial data onboarding comprises fundamentally distinct cognitive tasks: unstructured communications analysis, document note mining, entity onomastics, deterministic data aggregation, and invariant validation. Isolating these tasks into dedicated sub-agents prevents prompt degradation, enforces strict deterministic boundaries for financial math, and enables independent retry and confidence routing.
* **Orchestration**: `NevisSwarmOrchestrator` (`pipeline/swarm.py`) executes the agent DAG with a reflective feedback loop, callable via CLI (`python3 run_pipeline.py`) or REST API (`POST /api/pipeline/run`).

```
[Source Ingestion & Pre-Flight Validation]
                  ↓
[KnowledgeMiningAgent] (Slack rules extraction → SQLite vector index)
                  ↓
[DossierMinerAgent] (Notion CRM client & meeting notes mining)
                  ↓
[EntityResolverAgent] (Custodian holder disambiguation, trusts, joint accounts, onomastics)
                  ↓
[CanonicalTransformerAgent] (Collision-proof households, FX normalization, dual-metric AUM)
                  ↓
[AuditorReflectionAgent] ←─────── (Reflective Auto-Remediation Feedback Loop)
                  ↓
[ClarificationAgent] (Serializes canonical JSON & drafts customer-facing Round 2 message)
```

---

## 2. Implemented Multi-Agent Architecture

| Agent | Module | Base Class | Specialized Responsibility |
|---|---|---|---|
| `KnowledgeMiningAgent` | `pipeline/knowledge_layer.py` | `google.adk.BaseAgent` | Extracts institutional rules from Slack threads via Gemini, computes 768-dim embeddings (`text-embedding-004`), and maintains an indexed SQLite store with cosine deduplication (≥0.90 similarity updates existing rules). |
| `DossierMinerAgent` | `pipeline/doc_miner.py` | `google.adk.BaseAgent` | Mines unstructured client page dossiers and meeting notes for spousal relationships, entity affiliations, and unlisted prospect leads. |
| `EntityResolverAgent` | `pipeline/entity_resolver.py` | `google.adk.BaseAgent` | 8-step resolution cascade: exact matches (0.98), inverted names (0.96), trust grantors (0.95), joint co-holders (0.96), surname clusters (0.95), onomastic nicknames (0.95), CRM dossier affiliations (0.93), and gated LLM reasoning. |
| `CanonicalTransformerAgent` | `pipeline/transformer.py` | `google.adk.BaseAgent` | Synthesizes collision-proof households, normalizes accounts and interactions, executes benchmark FX conversions, computes dual-metric AUM, and attaches 1,067 field-level provenance audit trails. |
| `AuditorReflectionAgent` | `pipeline/auditor.py` | `google.adk.BaseAgent` | Evaluates Rules 1–8; executes reflective remediation to isolate anomalies and quarantine unresolvable records into triage queues. |
| `ClarificationAgent` | `pipeline/output_generator.py` | `google.adk.BaseAgent` | Serializes canonical JSON and formats customer-facing Round 2 Slack communication for operations leadership. |
| `NevisSwarmOrchestrator` | `pipeline/swarm.py` | `google.adk.BaseAgent` | Coordinates agent lifecycles, collects OpenTelemetry spans, and exports execution telemetry. |

---

## 3. Engineering Decisions & Architectural Trade-Offs

1. **Strict Deterministic vs. LLM Boundary**:
   * *Decision*: All financial arithmetic (AUM sums, balance rollups), FX multiplication, schema validation, and foreign-key referential checks are implemented in 100% deterministic Python code.
   * *Rationale*: Eliminates arithmetic hallucination. LLMs are restricted to qualitative analysis: extracting institutional lore, parsing unstructured notes, onomastic nickname resolution, and drafting stakeholder messages.
2. **Dual-Metric AUM Architecture (Canonical Rule 8)**:
   * *Decision*: Accounts retain custodian ground truth (`market_value_usd = $12,400.00` for Thompson), while household billing metrics enforce institutional rules (`active_aum_usd = $0.00` for inactive households).
   * *Rationale*: Satisfies custodian balance reconciliation and RIA operational billing reporting simultaneously without data corruption.
3. **Realistic Confidence Modeling (1,067 Tracked Fields)**:
   * *Decision*: Cross-system name matching without SSN/TIN verification carries `0.98` confidence (not 1.00). Household market value inherits the minimum resolution confidence of its constituent accounts (`min(account_confs)`: `0.95`–`0.98`).
   * *Rationale*: Reflects domain reality in wealth onboarding where custodian statements and CRM records are siloed external systems.
4. **Collision-Proof Household Synthesis**:
   * *Decision*: Unrelated clients sharing a surname without explicit CRM family links receive client-scoped household IDs (`HH-SURNAME-CLI-FIRSTNAME`).
   * *Rationale*: Avoids merging unrelated clients into a single household while grouping verified spouses.
5. **Zero-Dependency Spreadsheet Parser**:
   * *Decision*: Implemented in `pipeline/readers.py` using standard-library `zipfile` and streaming `xml.etree.ElementTree`.
   * *Rationale*: Eliminates third-party Excel dependencies (`openpyxl`, `pandas`), reducing attack surface, memory footprint, and environment conflicts.
6. **Local SQLite Knowledge & Vector Cache**:
   * *Decision*: Persisted in `outputs/knowledge_store.db` with pure Python cosine similarity calculations.
   * *Rationale*: Avoids external vector database infrastructure (Pinecone/Milvus); runs fully offline if network is unavailable.

---

## 4. Key Findings & Data Quirks

* **Notion Relational Flattening**: Notion exports export relational references (e.g., meeting `Client` column) as string titles rather than UUIDs. The pipeline resolves meeting client strings against Client records, linking upward to Households.
* **Historical Acquisition Lineage**: Harborline Advisors accounts tagged "Legacy" must map to canonical `ACTIVE` status while preserving an `"acquired from Harborline"` source tag.
* **Departed Personnel Suppression**: Service rep "A. Novak" (Anna Novak) left the firm in 2024. The pipeline detects departed staff and suppresses them from automated fallback assignments.
* **Multi-Currency Normalization**: Foreign holdings (e.g., Al-Rashid in EUR) are converted to USD at benchmark rates, retaining original currency codes.
* **Disambiguation vs. True Orphans**: Onomastic heuristics resolve "Bill Fitzgerald" $\rightarrow$ "William Fitzgerald" and "Bob Chen" $\rightarrow$ "Robert Chen". True orphans (`Carlos Vasquez`, `Priyanka Mehta`, and `Intro Call — Redwood Capital`) lack any CRM footprint and are quarantined for operator triage.

---

## 5. Assumptions Made & Justifications

* **Benchmark FX Rates**: Q2 2025 benchmark rates applied (USD=1.0, EUR=1.0710, CHF=1.1140, GBP=1.2680, CAD=0.7310). Unconfigured currencies log a warning, fall back to parity 1.0, and record the assumption in field provenance.
* **Prevailing As-Of Date**: Extracted dynamically from custodian records (`2025-06-30`).
* **Blank Advisor Tagging**: Unassigned households are marked `ADV-PENDING-CLARIFICATION` in canonical output, while proposing active service reps or senior advisors as recommended defaults in the Slack message.

---

## 6. Slack Business Rules Lifecycle & Runtime Governance

Institutional rules are extracted from `ops_slack_thread.md` via thread-segmented LLM extraction and indexed in SQLite with 768-dimensional embeddings for semantic retrieval.

| Rule ID | Guidance Extracted | Canonical Application | Governance & Correction Mechanism |
|---|---|---|---|
| `RULE_LEGACY_STATUS` | "Legacy = Harborline book, keep tag" | `Status='Legacy'` $\rightarrow$ `ACTIVE` + `source_tags: ["acquired from Harborline"]` | Update rule in SQLite; re-sync reapplies mapping. |
| `RULE_ADVISOR_PRECEDENCE` | "Don't guess if blank" | Prioritize Advisor column; forbid Service Rep fallback; route blanks to triage | Configurable `allow_service_rep_fallback` flag. |
| `RULE_DEPARTED_STAFF` | "A. Novak left, surface her" | Flag records referencing departed staff via `departed_staff_names` metadata | Update departed staff roster in knowledge layer. |
| `RULE_AUM_MARKET_VALUE` | "Market value always, ignore cost basis" | Aggregate custodian `Market_Value`; ignore `Cost_Basis` | Decoupled aggregation logic in `transformer.py`. |
| `RULE_FOREIGN_CURRENCY` | "Convert to USD, note that you did it" | FX conversion at benchmark rates; record `currency_original` | Update rates in `config.fx_rates_to_usd`. |
| `RULE_DEDUPLICATION` | "Known duplicate, collapse them" | Deduplication via `metadata.duplicate_variants` | Remove rule to split entities on next sync. |
| `RULE_CHURNED_CLIENT` | "Left in 2023, don't count toward AUM" | `status='INACTIVE'`, `active_aum_usd=0.0`, `market_value_usd=12400.0` | Setting status to `ACTIVE` restores billing AUM. |

### Automated Sync Application & Staleness Lifecycle
* **Automatic Encoding on Next Sync**: Rules extracted by `KnowledgeMiningAgent` are serialized as structured entities with 768-dimensional embeddings (`text-embedding-004`) into a persistent SQLite store (`outputs/knowledge_store.db`). On every subsequent sync execution (`python3 run_pipeline.py` or API run), `KnowledgeEngine.load_rules()` rehydrates these rules into memory before entity resolution, guaranteeing deterministic, zero-prompt reapplication across runs.
* **Correction When a Rule is Wrong**: 
  1. *Human-in-the-Loop Override*: When an operator corrects an assignment via the Web Dashboard or `POST /api/clarifications/resolve`, an authoritative `manual_override` rule is committed to SQLite, which takes absolute precedence over mined rules on future syncs.
  2. *Configuration Flags*: Architectural rules (e.g. advisor precedence, FX benchmarks) are decoupled into `config.py` (`allow_service_rep_fallback = False`), preventing pipeline-wide drift.
* **Staleness & Superseded Rules**: When the client updates their Slack thread or operations policy, re-running knowledge mining performs cosine similarity deduplication against existing embeddings. Rules matching $\ge 0.90$ semantic similarity update the existing record with an incremented version and timestamp rather than spawning duplicate or conflicting directives. Stale rules can also be marked inactive directly in SQLite.

---

## 7. Dual Modality: Headless CLI/API vs. Interactive Web Dashboard

1. **Headless CLI / API Mode** (`python3 run_pipeline.py` or `POST /api/pipeline/run`):
   * Designed for automated data syncs, scheduled cron jobs, and CI/CD validation.
   * Runs pre-flight validation, executes the multi-agent swarm, performs invariant audits, and outputs artifacts.
2. **Interactive Web Dashboard** (`python3 run_server.py` at `http://localhost:8000`):
   * Designed for Forward Deployed Engineers and RIA operations leads.
   * Provides drill-down inspection into all 1,067 field provenance records, visible confidence indicators across all entities, 1-click HITL resolution of open clarifications, live OpenTelemetry span visualizer, and file modification timestamp (`st_mtime`) auto-reload.

---

## 8. Distributed Tracing & Observability

* **Why OpenTelemetry**: Regulated wealth management environments require full execution explainability and audit readiness.
* **Implementation**: Uses standard `opentelemetry-api` and `opentelemetry-sdk` (`pipeline/telemetry.py`). Every agent phase (`agent.<name>`) and tool invocation (`tool.<name>`) emits structured spans tracking start/end timestamps, latency in milliseconds, execution status (`SUCCESS` / `ERROR`), and domain attributes.
* **Output**: All spans are exported to `outputs/telemetry_traces.json` and queryable via `GET /api/telemetry/traces`.

---

## 9. Summary of Deliverables

1. **`outputs/canonical_output.json`**:
   * 52 Households ($67,295,625.00 total MV, $67,283,225.00 active billing AUM).
   * 56 Clients, 51 Accounts, 7 Advisors, 17 Interactions.
   * 1,067 field-level `_provenance` records tracking source file, row number, method, confidence, rule/agent, and reasoning.
   * 100% compliance across all 8 canonical integrity rules.
2. **`outputs/clarifications_round2.md`**:
   * Customer-facing message to Dana Ruiz (Head of Operations).
   * Exactly 7 scoped, answerable items: 4 unassigned advisors (Delgado, Whitfield, Petit, Vandermeer), 2 unmapped custodian accounts (`CU-5010`, `CU-6025`), and 1 unregistered prospect meeting (Redwood Capital).
   * Structured format: **Trigger**, **Evidence**, **Candidate Options**, and **Proposed Default**, with a 1-line approval template.
3. **`outputs/telemetry_traces.json`**: Complete trace spans detailing all agent and tool invocations.
4. **`outputs/knowledge_store.db`**: SQLite database persisting institutional rules, vector embeddings, and operator resolutions.
