# Nevis FDE — DAG LLM Data Onboarding Platform

Modular DAG LLM onboarding pipeline built with the **Google Agent Development Kit (`google-adk` 2.8.0)** and **Google GenAI SDK** (`gemini-2.5-flash` + `text-embedding-004`), with distributed **OpenTelemetry** tracing and active reflective auditing. Ingests heterogeneous RIA records (Notion CRM, custodian XLSX, advisor roster, and Slack communications) into the Nevis canonical wealth schema with 1,067 field-level provenance audit trails.

---

## Quick Start

```bash
cd navis-takehome-navyansh-malhotra

# 1. Environment & Dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configuration (Optional: runs in deterministic offline mode if key omitted)
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here
```

### Running the Headless Pipeline (CLI)
To execute the automated ingestion, entity resolution, transformation, and audit pipeline:
```bash
python3 run_pipeline.py
```
* Validates source files, mines Slack rules and Notion dossiers, resolves custodian holders, calculates dual-metric AUM, audits all 8 canonical invariants, and writes deliverables to `outputs/`.
* Exits with code `0` on 100% rule compliance.

### Running the Interactive Web Dashboard & HITL Console (UI)
To launch the operational interface:
```bash
python3 run_server.py
# Open http://localhost:8000
```

#### What the UI Does & Why It's Needed
In real-world RIA onboarding, automated transformation requires operational review. The web dashboard serves as an interactive console for Forward Deployed Engineers and RIA operations leads:
1. **Inspect Field-Level Lineage**: Click any row in Households, Clients, Accounts, Advisors, or Interactions to open the slide-out provenance drawer. Displays source file, row location, extraction method, raw input value, reasoning, and confidence score.
2. **Resolve Clarifications Interactively (HITL)**: Triage the 7 unsettled discrepancies queued for Dana Ruiz (Head of Operations). Operators can confirm recommended defaults or assign advisors with 1 click. Resolutions persist directly to SQLite (`outputs/knowledge_store.db`) and reapply automatically on future syncs.
3. **Execute Live Pipeline Runs**: Click **"Execute Sync Pipeline"** in the masthead to re-run the DAG LLM pipeline from the browser. The server tracks file modification timestamps (`st_mtime`) and hot-reloads updated output files without restarting.
4. **Export Slack Communications**: View and copy the formatted Round 2 Slack message directly from the UI for posting to `#nevis-onboarding`.

### Testing a Clean Run From Scratch
To verify end-to-end execution without cached output artifacts:
```bash
rm -f outputs/canonical_output.json outputs/clarifications* outputs/telemetry_traces.json
python3 run_pipeline.py
# Or launch run_server.py and click "Execute Sync Pipeline" in the UI
```

---

## Deliverables Summary

| Deliverable | Location | Description |
|---|---|---|
| **Canonical Store** | `outputs/canonical_output.json` | 52 Households, 56 Clients, 51 Accounts, 7 Advisors, 17 Interactions with 1,067 field-level `_provenance` records. 100% compliance across 8 invariant rules. |
| **Round 2 Message** | `outputs/clarifications_round2.md` | Customer-ready follow-up to Dana Ruiz (Head of Operations) covering exactly 7 scoped questions (Trigger, Evidence, Options, Proposed Default). Concludes with a 1-line approval template. |
| **Design Specification** | `DESIGN.md` | DAG LLM pipeline topology, trade-offs, domain findings, and Slack rules lifecycle. |
| **Telemetry Traces** | `outputs/telemetry_traces.json` | OpenTelemetry spans tracking latency, status, and metadata across all pipeline stages and tools. |
| **Knowledge Store** | `outputs/knowledge_store.db` | SQLite store persisting extracted business rules, vector embeddings, and operator HITL resolutions. |

---

## DAG LLM Pipeline Architecture

Orchestrated via `NevisSwarmOrchestrator` (`pipeline/swarm.py`) as a modular Directed Acyclic Graph (DAG):

```
Source Ingestion → Knowledge Mining → Dossier Mining → Entity Resolution → Canonical Transformation → Reflective Audit → Deliverable Synthesis
                                                                 ^                                             |
                                                                 +---------------- (Auto-Remediation Loop) ----+
```

| Pipeline Stage / Agent | Module | Base Class | Specialized Role |
|---|---|---|---|
| `KnowledgeMiningAgent` | `pipeline/knowledge_layer.py` | `google.adk.BaseAgent` | Extracts Slack rules, generates 768-dim embeddings (`text-embedding-004`), deduplicates via cosine similarity. |
| `DossierMinerAgent` | `pipeline/doc_miner.py` | `google.adk.BaseAgent` | Mines Notion page bodies for spousal relationships, entity affiliations, and unregistered prospect leads. |
| `EntityResolverAgent` | `pipeline/entity_resolver.py` | `google.adk.BaseAgent` | 8-step resolution engine: exact matches, inverted names, trust grantors, affiliations, joint accounts, onomastics, and gated LLM disambiguation. |
| `CanonicalTransformerAgent` | `pipeline/transformer.py` | `google.adk.BaseAgent` | Synthesizes collision-proof households, normalizes accounts, executes FX conversion, calculates dual-metric AUM, and attaches field provenance. |
| `AuditorReflectionAgent` | `pipeline/auditor.py` | `google.adk.BaseAgent` | Audits Rules 1–8; executes reflective remediation loop to quarantine and re-route unmapped accounts and interactions. |
| `ClarificationAgent` | `pipeline/output_generator.py` | `google.adk.BaseAgent` | Serializes canonical JSON and drafts customer-ready Round 2 Slack message. |
| `NevisSwarmOrchestrator` | `pipeline/swarm.py` | `google.adk.BaseAgent` | Coordinates DAG pipeline lifecycle and collects OpenTelemetry execution spans. |

---

## Test Suite

```bash
# Invariant verification suite (exercises transformer and verifies Rules 1–8)
.venv/bin/python3 -m unittest tests/test_rules.py -v
```
