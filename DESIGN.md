# Design Note & Architectural Specification

## 1. Executive Overview & Framework Selection

The Nevis Agentic Data Onboarding Pipeline maps unstructured and heterogeneous RIA books of record (Notion CRM, custodian spreadsheets, advisor rosters, and Slack communications) into the Nevis canonical data model. 

* **Agent Framework**: **Google Agent Development Kit (`google-adk` 2.8.0)**.
* **Why Google ADK**: Built natively for production multi-agent orchestration, providing first-class agent state lifecycles, structured tool registration, and OpenTelemetry instrumentation without heavyweight framework bloat.
* **Why Multi-Agent Swarm (vs. Monolithic Prompt)**: Financial onboarding involves orthogonal cognitive tasks: institutional rule extraction, unstructured dossier parsing, legal entity onomastics, deterministic data aggregation, and invariant auditing. Decomposing these into specialized sub-agents isolates context windows, prevents prompt pollution, allows deterministic code where exact math is required, and enables independent retry and confidence routing.
* **Orchestration**: `NevisSwarmOrchestrator` (`pipeline/swarm.py`) coordinates the agent swarm across an execution DAG with an active reflective feedback loop. It is callable via CLI (`python3 run_pipeline.py`) or REST API (`POST /api/pipeline/run`).

```
[Ingestion & Validation] 
          ↓
[KnowledgeMiningAgent] (Extracts Slack rules into SQLite vector cache)
          ↓
[DossierMinerAgent] (Mines Notion client & meeting page bodies)
          ↓
[EntityResolverAgent] (Resolves custodian holders, trusts, LLCs, onomastics)
          ↓
[CanonicalTransformerAgent] (Synthesizes collision-proof households, FX, AUM)
          ↓
[AuditorReflectionAgent] ←─────── (Reflective Auto-Remediation Loop)
          ↓
[ClarificationAgent] (Generates canonical_output.json & clarifications_round2.md)
```

---

## 2. Implemented Architecture & Agent Roles

| Agent | Module | Base Class | Specialized Domain |
|---|---|---|---|
| `KnowledgeMiningAgent` | `pipeline/knowledge_layer.py` | `google.adk.BaseAgent` | Segments Slack conversations, extracts declarative business rules via Gemini, generates 768-dim embeddings (`text-embedding-004`), and indexes them in SQLite with cosine deduplication (≥0.90 similarity). |
| `DossierMinerAgent` | `pipeline/doc_miner.py` | `google.adk.BaseAgent` | Scans Notion client dossiers and meeting notes to extract spousal relationships, entity affiliations, and unregistered prospect leads. |
| `EntityResolverAgent` | `pipeline/entity_resolver.py` | `google.adk.BaseAgent` | 8-step resolution engine: exact matches, inverted names, trust grantors, dossier affiliations, joint co-holders, surname clusters, diminutives, and gated Gemini reasoning for complex entities. |
| `CanonicalTransformerAgent` | `pipeline/transformer.py` | `google.adk.BaseAgent` | Synthesizes collision-proof households, normalizes accounts and interactions, performs benchmark FX conversions, calculates dual-metric AUM, and attaches field-level provenance. |
| `AuditorReflectionAgent` | `pipeline/auditor.py` | `google.adk.BaseAgent` | Validates Rules 1–8; executes reflective remediation loop to quarantine and re-route unmapped accounts and interactions. |
| `ClarificationAgent` | `pipeline/output_generator.py` | `google.adk.BaseAgent` | Serializes canonical JSON with lineage metadata and drafts customer-ready Round 2 Slack message. |
| `NevisSwarmOrchestrator` | `pipeline/swarm.py` | `google.adk.BaseAgent` | Coordinates end-to-end swarm execution and collects OpenTelemetry trace spans. |

---

## 3. Decisions Made & Key Trade-Offs

1. **Strict Deterministic vs. LLM Boundary**:
   * *Decision*: All financial arithmetic (AUM sums, balance rollups), FX multiplication, schema typing, and referential foreign-key checks are implemented in 100% deterministic code.
   * *Trade-off*: LLMs are strictly reserved for qualitative reasoning (mining notes, entity onomastics, semantic plausibility, and message drafting). This eliminates arithmetic hallucination while maximizing contextual intelligence.
2. **Dual-Metric AUM Consistency (Canonical Rule 8)**:
   * *Decision*: Accounts retain custodian ground truth (`market_value_usd = $12,400.00` for Thompson), while household billing metrics enforce institutional rules (`active_aum_usd = $0.00` for inactive households).
   * *Trade-off*: Financial reconciliation against the custodian spreadsheet and RIA operational billing reporting are both preserved without contradiction.
3. **Zero-Guessing Policy & Confidence Routing**:
   * *Decision*: High-confidence resolutions (≥0.85) commit automatically into canonical records. Low-confidence matches (<0.50) are quarantined as structured items in `clarifications_round2.md`.
   * *Trade-off*: Eliminates silent mis-assignments. Natural person account holders with zero token overlap in the CRM (`Carlos Vasquez`, `Priyanka Mehta`) are never forced into arbitrary households.
4. **Collision-Proof Household Synthesis**:
   * *Decision*: Unrelated clients sharing a surname without explicit family links in CRM notes receive client-scoped household IDs (`HH-SURNAME-CLI-FIRSTNAME`).
   * *Trade-off*: Prevents accidental merging of distinct clients into a single household while still clustering verified spouses.
5. **Lightweight Vector & Rule Caching**:
   * *Decision*: SQLite database (`outputs/knowledge_store.db`) with math-based cosine similarity instead of heavy external vector databases.
   * *Trade-off*: Zero external infrastructure dependencies; runs completely offline if needed while supporting semantic similarity retrieval.

---

## 4. Key Findings & Data Quirks

* **Notion Relational Flattening**: Notion export relations (e.g., meeting `Client` column) flatten to string titles rather than database primary keys. The pipeline matches meeting client names to Client records, resolving upward to Households.
* **Historical Acquisition Lineage**: Clients tagged as "Legacy" from the 2019 Harborline Advisors acquisition must be mapped to canonical `ACTIVE` status while preserving an `"acquired from Harborline"` source tag.
* **Departed Personnel**: Service rep "A. Novak" (Anna Novak) left the firm in 2024. The pipeline detects departed staff and prevents falling back to them when an advisor is unassigned.
* **Multi-Currency Normalization**: Foreign-denominated holdings (e.g., Al-Rashid in EUR) are normalized to USD using benchmark quarter-end FX rates, retaining original currency metadata.
* **Disambiguation vs. True Orphans**: Onomastic reasoning resolves "Bill Fitzgerald" $\rightarrow$ "William Fitzgerald" and "Bob Chen" $\rightarrow$ "Robert Chen". True orphans (`Carlos Vasquez`, `Priyanka Mehta`, and `Intro Call — Redwood Capital`) have no CRM footprint and are quarantined for operator triage.

---

## 5. Assumptions Made & Justifications

* **Benchmark FX Rates**: Applied Q2 2025 benchmark rates (USD=1.0, EUR=1.0710, CHF=1.1140, GBP=1.2680, CAD=0.7310). If an unconfigured currency appears, the system logs a warning, falls back to parity 1.0, and flags the assumption in the field provenance reasoning.
* **Prevailing As-Of Date**: Dynamically extracted from custodian records (`2025-06-30`).
* **Blank Advisor Defaults**: When an advisor is blank, the record is tagged `ADV-PENDING-CLARIFICATION` in canonical output. For the customer-facing message to Dana, the pipeline proposes the active service rep or lead advisor as a recommended default for approval.

---

## 6. Slack Business Rules Lifecycle & Runtime Governance

Institutional rules are extracted from `ops_slack_thread.md` via thread-segmented LLM extraction and persisted in SQLite with 768-dimensional vector embeddings for semantic retrieval and cosine deduplication (≥0.90 similarity updates existing rules).

| Rule ID | Guidance Extracted | Canonical Encoding & Application | Lifecycle & Correction Mechanism |
|---|---|---|---|
| `RULE_LEGACY_STATUS` | "Legacy = Harborline book, keep tag" | `Status='Legacy'` $\rightarrow$ `ACTIVE` + `source_tags: ["acquired from Harborline"]` | Update rule in SQLite knowledge store; next sync reapplies mapping. |
| `RULE_ADVISOR_PRECEDENCE` | "Don't guess if blank" | Prioritize Advisor column; forbid Service Rep fallback; route blanks to clarifications | Configurable `allow_service_rep_fallback` policy flag. |
| `RULE_DEPARTED_STAFF` | "A. Novak left, surface her" | Flag records referencing departed staff via rule metadata `departed_staff_names` | Update departed staff roster in knowledge layer. |
| `RULE_AUM_MARKET_VALUE` | "Market value always, ignore cost basis" | Aggregate custodian `Market_Value`; ignore `Cost_Basis` | Decoupled aggregation logic in `transformer.py`. |
| `RULE_FOREIGN_CURRENCY` | "Convert to USD, note that you did it" | FX conversion at benchmark quarter-end rates; record `currency_original` | Update rates in `config.fx_rates_to_usd`. |
| `RULE_DEDUPLICATION` | "Known duplicate, collapse them" | Dynamic deduplication via `metadata.duplicate_variants` | Remove rule to split entities on next sync. |
| `RULE_CHURNED_CLIENT` | "Left in 2023, don't count toward AUM" | `status='INACTIVE'`, `active_aum_usd=0.0`, `market_value_usd=12400.0` | Setting status to `ACTIVE` restores billing AUM. |

**Runtime Governance**: Human-in-the-loop (HITL) decisions submitted via `POST /api/clarifications/resolve` persist as versioned `KnowledgeRule` records in SQLite, ensuring decisions survive server restarts and reapply automatically on future syncs.

---

## 7. Dual Modality: Headless CLI/API vs. Interactive Web Dashboard

The platform supports two operational modalities:
1. **Headless CLI / API Mode** (`python3 run_pipeline.py` or `POST /api/pipeline/run`):
   * Designed for automated data syncs, scheduled cron jobs, and CI/CD pipelines.
   * Runs pre-flight validation, executes the multi-agent swarm, performs the canonical integrity audit, and exports deliverables.
2. **Interactive Web Dashboard** (`python3 run_server.py` at `http://localhost:8000`):
   * Designed for Forward Deployed Engineers and RIA operations teams.
   * Displays high-level book metrics (Households, AUM, Accounts, Audit Status), interactive entity search with field-level provenance drilldown, live OpenTelemetry span visualizer, and a 1-click HITL resolution panel.

---

## 8. Distributed Tracing & Observability (Why OpenTelemetry)

* **Why OpenTelemetry**: Financial data pipelines operating in regulated RIA environments require complete explainability and performance transparency.
* **Implementation**: Uses standard `opentelemetry-api` and `opentelemetry-sdk` (`pipeline/telemetry.py`). Every agent phase (`agent.<name>`) and tool invocation (`tool.<name>`) emits structured spans tracking start/end timestamps, latency in milliseconds, execution status (`SUCCESS` / `ERROR`), and domain attributes.
* **Output**: All spans are exported to `outputs/telemetry_traces.json` and queryable via `GET /api/telemetry/traces`, enabling instant bottleneck detection and audit compliance.

---

## 9. Summary of Generated Deliverables

1. **`outputs/canonical_output.json`**:
   * 52 Households ($67,295,625.00 total MV, $67,283,225.00 active billing AUM).
   * 56 Clients, 51 Accounts, 7 Advisors, 17 Interactions.
   * Every field carries `_provenance` (source file, row, method, confidence, rule/agent, reasoning).
   * Passed 8 of 8 canonical integrity rules (100% compliance).
2. **`outputs/clarifications_round2.md`**:
   * Customer-facing follow-up Slack message to Dana Ruiz (Head of Operations).
   * Contains exactly 7 scoped, answerable items: 4 unassigned advisors (Delgado, Whitfield, Petit, Vandermeer), 2 unmapped custodian accounts (`CU-5010`, `CU-6025`), and 1 unregistered prospect meeting (Redwood Capital).
   * Each item includes: **Trigger**, **Evidence**, **Candidate Options**, and **Proposed Default**.
   * Concludes with a 1-line approval template allowing Dana to reply with minimal effort.
3. **`outputs/telemetry_traces.json`**: Complete trace spans detailing all agent and tool invocations.
4. **`outputs/knowledge_store.db`**: SQLite database persisting institutional rules and vector embeddings.
