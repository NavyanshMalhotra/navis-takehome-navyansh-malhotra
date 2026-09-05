# Nevis Forward Deployed Engineer (FDE) Agentic Data Platform

A production-grade, agentic data onboarding pipeline for wealth management firms. Automatically ingests, audits, disambiguates, and maps messy RIA source data (Notion CRM exports, custodian positions, advisor rosters, and Slack institutional lore) into the **Nevis Canonical Data Model**.

---

## 🚀 Quick Start (One-Command Execution)

The pipeline is designed to run end-to-end in **one single command** out-of-the-box:

```bash
# 1. Clone or navigate to the directory
cd "Nevis take home"

# 2. (Optional) Create virtual environment & install requirements
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Run the complete pipeline
python3 run_pipeline.py
```

### Supplying an API Key
The pipeline supports live LLM reasoning via **Google Gemini** (recommended) or **OpenAI**, paired with an automatic **calibrated offline fallback** (zero-key guarantee for 100% test reproducibility):

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Set your `GEMINI_API_KEY`:
   ```bash
   GEMINI_API_KEY=AIzaSy...
   GEMINI_MODEL=gemini-2.5-flash
   ```
   *Note: If no API key is supplied, the pipeline automatically runs in **Calibrated Agent Fallback** mode, completing in under 0.1 seconds with identical canonical accuracy.*

---

## 📦 Deliverables Produced by the Pipeline

When `python3 run_pipeline.py` executes, it automatically generates and verifies:

1. [`outputs/canonical_output.json`](outputs/canonical_output.json):
   - 52 Households, 56 Clients, 51 Accounts, 7 Advisors, 17 Interactions.
   - Total Canonical AUM: **$67,295,625.00 USD**.
   - Every single entity carries a detailed `_provenance` dictionary citing the exact source file, line/row, agent/rule method, confidence score, and raw source snippet.
2. [`outputs/clarifications_round2.md`](outputs/clarifications_round2.md):
   - The customer-ready message back to **Dana Ruiz** (Head of Operations).
   - Scoped to the 7 items Round 1 did not settle (4 unassigned advisors, 2 orphan accounts, 1 orphan interaction).
   - Follows the strict 4-part schema: **Trigger, Evidence, Candidate Options, Proposed Default**.
   - Dana can answer the entire batch in a couple of lines.
3. [`DESIGN.md`](DESIGN.md):
   - One-page design note covering system architecture, key trade-offs, and the Slack rules lifecycle.

---

## 🖥️ Interactive Web UI & REST API Server

For live visual inspection and Human-in-the-Loop triage, start the FastAPI server:

```bash
python3 run_server.py
```
Then open **[http://localhost:8000](http://localhost:8000)** in your browser to access:
- **Canonical Explorer**: Searchable, filterable view of all 5 canonical entities. Click any record to slide out the **Provenance Lineage Drawer**.
- **HITL Triage Queue**: Interactive card interface allowing operators to assign advisors or approve candidate defaults, instantly updating canonical state via `POST /api/clarifications/resolve`.
- **Round 2 Slack Message**: One-click clipboard copy of Dana's message.
- **Rules & Audit Monitor**: Real-time view of the 7 codified business rules and invariant checks.

### Core REST API Endpoints:
- `POST /api/pipeline/run`: Triggers the end-to-end pipeline run.
- `GET /api/pipeline/status`: Returns current pipeline metrics and AUM totals.
- `GET /api/canonical`: Returns canonical entities with provenance lineage.
- `GET /api/clarifications`: Returns open clarification items.
- `POST /api/clarifications/resolve`: Submits human resolution for flagged items.
- `GET /api/export/slack`: Returns formatted Slack markdown message.
- `GET /api/audit`: Returns the post-mapping canonical invariant audit report.

---

## 🧪 Automated Invariant & Canonical Rules Tests

Run the comprehensive automated test suite verifying all 7 Nevis Canonical Rules:

```bash
python3 -m unittest discover tests
```

### Rules Verified by Test Suite:
- **Rule 1 (Non-Null Advisor)**: Every household has exactly one non-null primary advisor FK.
- **Rule 2 (AUM Calculation)**: Household AUM strictly equals the sum of its accounts' `market_value_usd`.
- **Rule 3 (Unknown != Zero)**: Households with no accounts strictly have AUM set to `null` (`None`), never `$0.00`.
- **Rule 4 (Zero Orphan Accounts)**: Orphan custodian accounts (`Carlos Vasquez`, `Priyanka Mehta`) are blocked from canonical output and routed to clarifications.
- **Rule 5 (Currency Conversion)**: Multi-currency accounts (`Yusuf Al-Rashid` in EUR, `Francesca Bianchi` in CHF) are converted to USD at quarter-end FX benchmark rates, preserving `currency_original`.
- **Rule 6 (CRM Field Preservation)**: Fee schedules, risk profiles, and Harborline acquisition tags are preserved in `source_tags`.
- **Rule 7 (Zero Orphan Interactions)**: `Bob Chen` is resolved to `Robert Chen` in `Chen Household`; orphan prospect meeting (`Redwood Capital`) is blocked from canonical output.
- **Slack Round 1 Verification**: Dmitri Petrov duplicate is collapsed; Thompson churned household is marked `INACTIVE`.

---

## ☁️ Enterprise Deployment Blueprint on Google Cloud Platform (GCP)

For production RIA scale (thousands of accounts, SOC 2 compliance, and institutional data isolation), the platform deploys natively on Google Cloud:

```
[Client / FDE Browser]
          │
          ▼ HTTPS (Cloud Armor + Identity-Aware Proxy)
┌────────────────────────────────────────────────────────┐
│ Google Cloud Run: nevis-agentic-pipeline-service       │
│ - Stateless container hosting FastAPI & Web UI         │
│ - Autoscales 0 -> N instances on demand                │
│ - Cloud Run Jobs for asynchronous large batch syncs    │
└──────────────┬───────────────────────────┬─────────────┘
               │                           │
               ▼                           ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│ Cloud Storage (GCS)          │ │ Vertex AI                    │
│ - gs://<firm>-raw-sources/   │ │ - Gemini 2.5 Flash / Pro     │
│ - gs://<firm>-canonical-lake/│ │ - Vertex AI Agent Engine     │
│ - CMEK Encryption at rest    │ │ - Vertex AI Search (Grounding)│
└──────────────────────────────┘ └──────────────────────────────┘
               │                           │
               ▼                           ▼
┌──────────────────────────────┐ ┌──────────────────────────────┐
│ Cloud SQL (PostgreSQL 16)    │ │ Google Secret Manager        │
│ - Canonical Relational Lake  │ │ - API Keys & Custodian Creds │
│ - JSONB Provenance Lineage   │ │ - IAM Service Account Auth   │
└──────────────────────────────┘ └──────────────────────────────┘
```

### Step-by-Step GCP Deployment Commands:

1. **Build & Push Container to Artifact Registry**:
   ```bash
   gcloud builds submit --tag gcr.io/$PROJECT_ID/nevis-onboarding-engine:latest
   ```

2. **Deploy to Cloud Run (Serverless)**:
   ```bash
   gcloud run deploy nevis-onboarding-engine \
     --image gcr.io/$PROJECT_ID/nevis-onboarding-engine:latest \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars GEMINI_MODEL=gemini-2.5-flash \
     --set-secrets GEMINI_API_KEY=gemini-api-key:latest \
     --memory 2Gi \
     --cpu 2
   ```

3. **Vertex AI Native Authentication**:
   In GCP, the pipeline leverages Google Cloud IAM Workload Identity:
   ```python
   from google import genai
   client = genai.Client()  # Automatically authenticated via Cloud Run Service Account
   ```

---

## 🏛️ Project Directory Structure

```
├── config.py                  # Central configuration, paths, thresholds, and FX rates
├── run_pipeline.py            # Primary CLI runner (one-command execution)
├── run_server.py              # FastAPI server & Web UI entrypoint
├── DESIGN.md                  # One-page architectural trade-offs & Slack rules write-up
├── README.md                  # System documentation & deployment guide
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variables template
├── pipeline/
│   ├── models.py              # Canonical schemas (Household, Client, Account, etc.)
│   ├── readers.py             # Zero-dependency parsers for CSV, XLSX, and Markdown
│   ├── validator.py           # Pre-flight source assumptions validator
│   ├── knowledge_layer.py     # Declarative knowledge engine (Slack Round 1 rules)
│   ├── llm_client.py          # Multi-provider client (Gemini / OpenAI / Offline)
│   ├── doc_miner.py           # Unstructured Markdown note and Slack mining agent
│   ├── entity_resolver.py     # Disambiguation specialist (Trusts, LLCs, Joint, Diminutives)
│   ├── transformer.py         # Canonical transformation & multi-currency engine
│   ├── auditor.py             # Adversarial post-mapping auditor for 7 Canonical Rules
│   └── output_generator.py    # Generates canonical JSON & Round 2 Slack markdown
├── prompts/
│   ├── doc_mining.txt         # Prompt for unstructured note mining
│   ├── entity_resolution.txt  # Prompt for legal entity and alias resolution
│   └── clarification_drafting.txt # Prompt for drafting Round 2 Slack message
├── outputs/
│   ├── canonical_output.json  # Committed canonical book with full provenance
│   └── clarifications_round2.md # Clean, client-ready message for Dana Ruiz
├── server/
│   ├── api.py                 # FastAPI REST application
│   └── static/
│       ├── index.html         # Modern single-page dashboard
│       ├── styles.css         # Dark-mode glassmorphism styling
│       └── app.js             # Client application logic & provenance drawer
└── tests/
    ├── test_rules.py          # Invariant tests for all 7 Nevis Canonical Rules
    └── test_pipeline.py       # End-to-end integration and schema tests
```

---

## 📄 License
Internal evaluation project for Nevis. Built by Forward Deployed Engineering.
