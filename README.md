# Nevis FDE — Agentic Data Onboarding Pipeline

Staged multi-agent pipeline built on the **Google GenAI SDK** (`gemini-2.5-flash` + `text-embedding-004`). Ingests messy RIA source data (Notion CRM, custodian XLSX, advisor roster, Slack institutional lore) and maps it into the Nevis canonical data model.

**Agent framework choice**: Custom Python agents on the native Google GenAI SDK. Wealth management onboarding is half deterministic arithmetic (FX conversion, foreign keys, schema validation) and half contextual judgment (entity disambiguation, note mining, confidence routing). A direct SDK integration gives precise control over both without framework overhead.

---

## Quick Start

```bash
cd navis-takehome-navyansh-malhotra

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Set GEMINI_API_KEY=your_key_here

python3 run_pipeline.py
```

The pipeline degrades gracefully without an API key: deterministic resolution (name matching, FX conversion, schema enforcement) still runs. LLM-dependent steps (note mining, ambiguous entity disambiguation, clarification drafting) produce conservative defaults.

---

## Outputs

1. **`outputs/canonical_output.json`** — Canonical records with field-level `_provenance` (source file, row, method, confidence, reasoning).

2. **`outputs/clarifications_round2.md`** — Round 2 message to Dana Ruiz. Each item has: Trigger, Evidence, Candidate Options, Proposed Default. Does not re-ask anything settled in Round 1.

3. **`DESIGN.md`** — Architecture and Slack rules lifecycle.

---

## Pipeline Stages

```
Ingestion → Validation → Knowledge Extraction → Transformation → Audit → Output
```

| Stage | Module | LLM? | Purpose |
|-------|--------|------|---------|
| Ingestion | `readers.py` | No | Parse CSV, XLSX, Markdown with zero external dependencies |
| Validation | `validator.py` | No | Pre-flight schema and data format checks |
| Knowledge | `knowledge_layer.py` | Yes | Extract Slack rules, vector-embed, deduplicate via cosine similarity |
| Doc Mining | `doc_miner.py` | Yes | Mine Notion page bodies for spousal links, corporate entities, notes |
| Entity Resolution | `entity_resolver.py` | Yes | Map custodian account holders to households (trusts, joint accounts, nicknames) |
| Transformation | `transformer.py` | No | Build canonical entities, enforce foreign keys, FX conversion, dual-metric AUM |
| Audit | `auditor.py` | Optional | Validate Rules 1–8, semantic plausibility checks |
| Output | `output_generator.py` | Optional | Serialize canonical JSON, draft Round 2 clarifications |

---

## Tests

```bash
python3 -m pytest tests/ -v
```

---

## Web UI & REST API

```bash
python3 run_server.py
# Open http://localhost:8000
```

### Endpoints
- `POST /api/pipeline/run` — Execute pipeline
- `GET /api/canonical` — Canonical entities with provenance
- `GET /api/clarifications` — Open/resolved clarification items
- `POST /api/clarifications/resolve` — Resolve items (persisted to SQLite)
- `GET /api/audit` — Audit report
- `GET /api/export/slack` — Formatted Slack markdown
