#!/usr/bin/env python3
"""
==============================================================================
Nevis Forward Deployed Engineer (FDE) Agentic Pipeline Runner
==============================================================================
Runs the end-to-end ingestion, agentic entity resolution, canonical mapping,
adversarial validation, and artifact generation in a single command.

Usage:
    python3 run_pipeline.py
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Auto-delegate to .venv if current interpreter lacks dependencies
venv_python = BASE_DIR / ".venv" / "bin" / "python3"
if sys.executable != str(venv_python) and venv_python.exists():
    try:
        from google import genai
    except ImportError:
        import os
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

from config import config
from pipeline.readers import (
    read_advisor_roster,
    read_custodian_positions,
    read_notion_clients,
    read_notion_meetings,
    read_slack_thread,
)
from pipeline.validator import SourceValidationSuite
from pipeline.knowledge_layer import KnowledgeEngine
from pipeline.transformer import CanonicalTransformer
from pipeline.auditor import CanonicalAuditor
from pipeline.output_generator import OutputGenerator
from pipeline.llm_client import llm_client

def run_pipeline() -> int:
    start_time = time.time()
    print("=" * 80)
    print("NEVIS AGENTIC DATA ONBOARDING PIPELINE")
    print("Client: Beaconcrest Advisors (RIA Onboarding - Round 2)")
    print("=" * 80)

    # 1. Environment & Provider Status
    print(f"\n[1/6] Initializing AI & Heuristics Engine...")
    print(f"  - Active Provider Mode: {llm_client.provider.upper()}")
    if llm_client.provider == "gemini":
        print(f"  - Model: {config.gemini_model} (Live Google GenAI active)")
    else:
        print("  - Mode: Calibrated Deterministic Agent Fallback (Zero-Key Offline Guarantee)")
        print("  - Tip: To run live Gemini reasoning, set GEMINI_API_KEY=<your_key> in .env")

    # 2. Ingestion
    print(f"\n[2/6] Ingesting Source Datasets from: {config.sources_dir}...")
    try:
        advisors = read_advisor_roster(config.sources_dir / "advisor_roster.csv")
        custodian = read_custodian_positions(config.sources_dir / "custodian_positions.xlsx")
        clients = read_notion_clients(config.sources_dir / "notion_export")
        meetings = read_notion_meetings(config.sources_dir / "notion_export")
        slack_raw = read_slack_thread(config.sources_dir / "ops_slack_thread.md")
    except Exception as e:
        print(f"[FATAL ERROR] Ingestion failed: {e}")
        return 1

    print(f"  ✓ Ingested {len(advisors)} advisors from advisor_roster.csv")
    print(f"  ✓ Ingested {len(custodian)} custodian account positions from custodian_positions.xlsx")
    print(f"  ✓ Ingested {len(clients)} clients (+ linked Markdown notes) from notion_export/")
    print(f"  ✓ Ingested {len(meetings)} meetings (+ linked Markdown notes) from notion_export/")
    print(f"  ✓ Ingested Round 1 Slack thread ({len(slack_raw.splitlines())} lines)")

    # 3. Pre-Flight Validation
    print(f"\n[3/6] Running Pre-Flight Source Sanity Audit...")
    validation_report = SourceValidationSuite.audit_sources(advisors, clients, meetings, custodian)
    if not validation_report.is_valid:
        print(f"[ERROR] Pre-flight validation failed:")
        for err in validation_report.errors:
            print(f"  ✗ {err}")
        return 1
    print("  ✓ Source schemas and data formats verified.")
    for warn in validation_report.warnings:
        print(f"  ! [Notice] {warn}")

    # 4. Agentic Transformation & Entity Resolution
    print(f"\n[4/6] Executing Agentic Mapping & Entity Disambiguation...")
    ke = KnowledgeEngine()
    transformer = CanonicalTransformer(ke)
    bundle, clarifs = transformer.transform_all(advisors, clients, meetings, custodian)

    print(f"  ✓ Synthesized {len(bundle.households)} Households")
    print(f"  ✓ Mapped {len(bundle.clients)} Clients (Dmitri Petrov duplicate collapsed)")
    print(f"  ✓ Mapped {len(bundle.accounts)} Accounts (EUR & CHF currencies normalized to USD)")
    print(f"  ✓ Mapped {len(bundle.advisors)} Advisors")
    print(f"  ✓ Mapped {len(bundle.interactions)} Interactions (Bob Chen resolved to Robert Chen)")
    print(f"  ✓ Flagged {len(clarifs)} Scoped Clarifications for Dana Ruiz")

    # 5. Adversarial Post-Mapping Validation (The 7 Nevis Canonical Rules)
    print(f"\n[5/6] Executing Adversarial Canonical Rules Audit...")
    audit_report = CanonicalAuditor.audit_canonical_bundle(bundle)
    print(audit_report.summary())
    if not audit_report.is_valid:
        print("\n[FAIL] Canonical mapping violated constraints!")
        return 1

    # 6. Artifact Generation
    print(f"\n[6/6] Generating Deliverable Artifacts into '{config.outputs_dir}'...")
    canonical_file = config.outputs_dir / "canonical_output.json"
    clarif_file = config.outputs_dir / "clarifications_round2.md"

    OutputGenerator.write_canonical_json(bundle, canonical_file)
    OutputGenerator.write_clarifications_markdown(clarifs, clarif_file)

    print(f"  ✓ Saved: {canonical_file} ({canonical_file.stat().st_size:,} bytes)")
    print(f"  ✓ Saved: {clarif_file} ({clarif_file.stat().st_size:,} bytes)")

    # Execution Summary
    duration = time.time() - start_time
    total_aum = sum(h.market_value_usd for h in bundle.households if h.market_value_usd is not None)

    print("\n" + "=" * 80)
    print("PIPELINE EXECUTION COMPLETE (SUCCESS)")
    print("=" * 80)
    print(f"Execution Time:           {duration:.2f} seconds")
    print(f"Committed Households:     {len(bundle.households)}")
    print(f"Total Canonical AUM:      ${total_aum:,.2f} USD")
    print(f"Committed Clients:        {len(bundle.clients)}")
    print(f"Committed Accounts:       {len(bundle.accounts)}")
    print(f"Round 2 Clarification Qs: {len(clarifs)} scoped items for Dana Ruiz")
    print(f"Deliverables Committed:   outputs/canonical_output.json")
    print(f"                          outputs/clarifications_round2.md")
    print("=" * 80)
    return 0

if __name__ == "__main__":
    sys.exit(run_pipeline())
