# Nevis FDE — Agentic Data Onboarding Pipeline

Multi-agent swarm built on the **Google Agent Development Kit (`google-adk` 2.8.0)** and **Google GenAI SDK** (`gemini-2.5-flash` + `text-embedding-004`) with distributed **OpenTelemetry** tracing and active reflective auditing. Ingests messy RIA source data (Notion CRM, custodian XLSX, advisor roster, Slack institutional lore) and maps it into the Nevis canonical data model.

**Agent framework choice**: **Google ADK (`google-adk` 2.8.0)**. Coordinates a specialized swarm of agents (`KnowledgeMiningAgent`, `DossierMinerAgent`, `EntityResolverAgent`, `CanonicalTransformerAgent`, `AuditorReflectionAgent`, `ClarificationAgent`) via `NevisSwarmOrchestrator`, instrumented with OpenTelemetry distributed tracing and reflective integrity audits.

---

## Quick Start

```bash
cd navis-takehome-navyansh-malhotra

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Set GEMINI_API_KEY=your_key_here (optional; runs in offline deterministic mode if omitted)

python3 run_pipeline.py
```

The pipeline degrades gracefully without an API key: deterministic resolution (name matching, offline onomastic dictionary, FX conversion, schema enforcement) still runs. LLM-dependent steps (note mining, ambiguous entity disambiguation, clarification drafting) produce conservative defaults.

---

## Outputs

1. **`outputs/canonical_output.json`** — Canonical records with field-level `_provenance` (source file, row, method, confidence, reasoning).
2. **`outputs/clarifications_round2.md`** — Round 2 message to the operations lead. Each item has: Trigger, Evidence, Candidate Options, Proposed Default. Does not re-ask anything settled in Round 1.
3. **`DESIGN.md`** — Architecture, agent swarm topology, and Slack rules lifecycle.

---

## Agent Swarm Architecture

```
Ingestion & Sanity → Knowledge Mining → Dossier Mining → Entity Resolution → Canonical Transformation → Reflective Audit → Deliverable Synthesis
                                                                 ^                                             |
                                                                 +---------------- (Feedback Loop) ------------+
```

| Agent | Module | Base Class | Purpose |
|-------|--------|------------|---------|
| `KnowledgeMiningAgent` | `pipeline/knowledge_layer.py` | `google.adk.BaseAgent` | Extracts Slack rules, vector-embeds, deduplicates via cosine similarity |
| `DossierMinerAgent` | `pipeline/doc_miner.py` | `google.adk.BaseAgent` | Mines Notion client dossiers and meeting notes for latent links |
| `EntityResolverAgent` | `pipeline/entity_resolver.py` | `google.adk.BaseAgent` | Disambiguates legal entities, trusts, joint accounts, and onomastic nicknames |
| `CanonicalTransformerAgent` | `pipeline/transformer.py` | `google.adk.BaseAgent` | Synthesizes collision-proof households, normalizes accounts, FX conversion, dual-metric AUM |
| `AuditorReflectionAgent` | `pipeline/auditor.py` | `google.adk.BaseAgent` | Audits Rules 1–8 and triggers reflective remediation on anomalies |
| `ClarificationAgent` | `pipeline/output_generator.py` | `google.adk.BaseAgent` | Serializes canonical JSON and drafts Round 2 clarification document |
| `NevisSwarmOrchestrator` | `pipeline/swarm.py` | `google.adk.BaseAgent` | Swarm orchestrator coordinating execution and OpenTelemetry telemetry |

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

---

## Web UI & REST API

```bash
python3 run_server.py
# Open http://localhost:8000
```

### Endpoints
- `POST /api/pipeline/run` — Execute Google ADK swarm pipeline
- `GET /api/canonical` — Canonical entities with field-level provenance
- `GET /api/clarifications` — Open and resolved clarification items
- `POST /api/clarifications/resolve` — Resolve items (persisted to SQLite knowledge store)
- `GET /api/audit` — Canonical integrity audit report
- `GET /api/telemetry/traces` — OpenTelemetry recorded spans and execution metrics
- `GET /api/export/slack` — Formatted Slack markdown
