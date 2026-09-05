# Nevis Forward Deployed Engineer (FDE) - Agentic Data Onboarding Pipeline

A ReAct multi-agent data onboarding pipeline designed for wealth management RIAs. Ingests, audits, disambiguates, and maps unstandardized source data (Notion CRM exports, custodian positions, advisor rosters, and Slack institutional lore) into the **Nevis Canonical Data Model**.

---

## 1. Quick Start

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Google Gemini API key (supports AI Studio `AIza...` and Google Cloud Vertex AI Express keys `AQ...`)

```bash
# 1. Clone or navigate to the repository
cd navis-takehome-navyansh-malhotra

# 2. Set up virtual environment and install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure API key
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here

# 4. Run the pipeline
python3 run_pipeline.py
```

> **API Key Requirement**: The pipeline relies on live LLM reasoning via Google Gemini (`gemini-2.5-flash`) for unstructured text mining, legal entity disambiguation, and draft synthesis, as well as Google's `text-embedding-004` endpoint for vector embeddings of institutional lore. If the key is missing or invalid, execution halts with an explicit configuration error rather than silently generating unverified data.

---

## 2. Deliverables Produced

Execution generates and validates three primary deliverables:

1. [`outputs/canonical_output.json`](outputs/canonical_output.json):
   - **52 Households, 56 Clients, 50 Accounts, 7 Advisors, 17 Interactions**.
   - **Total Custodian Market Value**: **$66,415,625.00 USD**.
   - **Active Billing AUM**: **$66,403,225.00 USD** (reflects Rule 8: $12,400 excluded for churned Thompson household).
   - Every entity includes an explicit `_provenance` dictionary citing the source file, row/line, resolving agent, confidence score, and extracted text evidence.
   - 2 orphan custodian accounts (`Carlos Vasquez`, `Priyanka Mehta`) and 1 orphan interaction (`Redwood Capital`) are withheld from the canonical store and routed to clarifications.

2. [`outputs/clarifications_round2.md`](outputs/clarifications_round2.md):
   - Client-ready message addressed to **Dana Ruiz** (Head of Operations).
   - Scoped strictly to the 8 unresolved items: 4 unassigned advisor households, 2 orphan accounts, 1 orphan prospect meeting, and 1 departed contractor reference.
   - Structured into 4 parts per item: **Trigger, Evidence, Candidate Options, Proposed Default**.

3. [`DESIGN.md`](DESIGN.md):
   - One-page technical note detailing the ReAct multi-agent graph architecture, unified Google embedding endpoint, local SQLite caching vs Cloud SQL (`pgvector`) persistence, dual-metric active AUM, and the Slack rules lifecycle.

---

## 3. ReAct Multi-Agent Graph Architecture

The pipeline executes as a multi-agent system where specialized agents communicate over a shared blackboard state and invoke deterministic tools:

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
│                                     │ AuditorAgent        │──┐ (Reflective Feedback Loop)            │
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

### Agents & Responsibilities
- **KnowledgeAgent**: Ingests Slack lore (`ops_slack_thread.md`), uses Gemini to extract declarative rules, computes 768-dim embeddings via Google's `text-embedding-004` endpoint, and indexes them in a local SQLite cache (`outputs/knowledge_store.db`).
- **DocMinerAgent**: Reads unstructured Markdown notes (`client_notes.md`, `meeting_notes.md`), extracting corporate entities (e.g. `Nakamura Holdings LLC`), spousal relationships, and operational flags with exact source citations.
- **EntityResolverAgent**: Resolves entity linkages, trusts, joint accounts, and name variations using deterministic normalization and LLM disambiguation.
- **MappingAgent**: Constructs canonical schemas, enforces foreign keys, executes multi-currency conversions to USD at benchmark quarter-end FX rates, and computes dual-metric AUM.
- **AuditorAgent**: Evaluates 8 canonical rules and performs semantic plausibility checks. Can reject transformations and trigger feedback cycles.
- **ClarificationAgent**: Synthesizes open discrepancies into a structured Round 2 Slack communication for operations.

---

## 4. Canonical Rules Enforced

The pipeline audits and guarantees compliance across 8 canonical rules:

- **Rule 1 (Non-Null Advisor)**: Every household has a valid primary advisor FK. Unassigned households are routed to clarifications with proposed defaults.
- **Rule 2 (AUM Calculation)**: Household `market_value_usd` strictly equals the sum of its associated account balances.
- **Rule 3 (Unknown != Zero)**: Households with no custodial accounts have AUM set to `null`, never `$0.00`.
- **Rule 4 (Zero Orphan Accounts)**: Custodian accounts with unresolvable household associations are withheld from canonical output and flagged in triage.
- **Rule 5 (Currency Conversion)**: Non-USD accounts (EUR, CHF) are converted at quarter-end benchmark FX rates; original currency is preserved in `currency_original`.
- **Rule 6 (CRM Field Preservation)**: Non-standard Notion attributes (fee schedules, risk profiles, Harborline acquisition tags) are retained in `source_tags`.
- **Rule 7 (Zero Orphan Interactions)**: Interactions link to valid client/household records; orphan prospect meetings are held in triage.
- **Rule 8 (Active Billing AUM vs Custodian Market Value)**: Custodian balances are preserved for balance-sheet reconciliation (`market_value_usd = 12400.0`), but inactive/churned households strictly yield `active_aum_usd = 0.0`.

---

## 5. Automated Tests

Execute the unit and integration test suite:

```bash
python3 -m unittest discover tests
```

---

## 6. Inspection Web UI & REST API Server

A local server is included for human-in-the-loop inspection and triage:

```bash
python3 run_server.py
```
Open **[http://localhost:8000](http://localhost:8000)** to view:
- **Canonical Data Book**: Filterable, data-dense view of all canonical entities. Clicking any row opens the provenance drawer showing source citations and confidence.
- **Triage & Clarifications Queue**: Triage interface for assigning advisors or confirming candidate defaults.
- **Slack Round 2 Draft**: Customer-ready message ready for export.
- **Rules & Audit Log**: Verification statuses for Rules 1 through 8.

### Core REST Endpoints
- `POST /api/pipeline/run`: Executes the end-to-end pipeline.
- `GET /api/canonical`: Returns canonical entities with provenance lineage.
- `GET /api/clarifications`: Returns open clarification items.
- `POST /api/clarifications/resolve`: Resolves clarification items and applies overrides.
- `GET /api/audit`: Returns the post-mapping audit report.
- `GET /api/export/slack`: Returns formatted Slack markdown text.

---

## 7. Cloud Deployment Architecture (GCP)

In production RIA environments, the service deploys as a containerized workload on Google Cloud:
- **Google Cloud Run**: Serverless container hosting the FastAPI service and Web UI.
- **Cloud SQL (PostgreSQL with `pgvector`)**: Persistent storage for canonical entities and vector embeddings of institutional lore.
- **Google Vertex AI**: Enterprise Gemini 2.5 Flash and `text-embedding-004` endpoints authenticated via Cloud Run IAM Workload Identity (no static API keys).
- **Google Cloud Storage (GCS)**: Source document and export artifact repository.
