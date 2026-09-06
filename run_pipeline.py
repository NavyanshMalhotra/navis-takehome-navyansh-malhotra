#!/usr/bin/env python3
"""
Nevis Forward Deployed Engineer (FDE) Pipeline Runner.
Orchestrates the Google ADK Multi-Agent Swarm for wealth data onboarding
with OpenTelemetry tracing, reflective auditing, and artifact generation.

Usage:
    python3 run_pipeline.py
"""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Auto-delegate to .venv if current interpreter lacks dependencies
venv_python = BASE_DIR / ".venv" / "bin" / "python3"
if sys.executable != str(venv_python) and venv_python.exists():
    try:
        from google import genai
        import google.adk
    except ImportError:
        import os
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)

from config import config
from pipeline.swarm import NevisSwarmOrchestrator
from pipeline.llm_client import llm_client


def run_pipeline() -> int:
    print("=" * 80)
    print("NEVIS AGENTIC DATA ONBOARDING PIPELINE (GOOGLE ADK SWARM)")
    print(f"Target Firm: {config.firm_name}")
    print("=" * 80)

    if llm_client.is_available:
        print(f"Provider: Google GenAI ({config.gemini_model}, text-embedding-004)")
    else:
        print("Provider: Offline Deterministic Fallback Mode (Set GEMINI_API_KEY for live reasoning)")

    orchestrator = NevisSwarmOrchestrator()
    print("\nExecuting Google ADK Agent Swarm...")
    try:
        result = orchestrator.run(write_artifacts=True)
    except Exception as exc:
        print(f"\n[ERROR] Swarm execution failed: {exc}")
        return 1

    bundle = result.bundle
    clarifs = result.clarifications
    audit = result.audit_report
    tel = result.telemetry_summary

    print("\n" + audit.summary())

    if not audit.is_valid:
        print("\n[FAIL] Canonical integrity constraints violated.")
        return 1

    total_mv = bundle.metadata.get("total_market_value_usd", 0.0)
    active_aum = bundle.metadata.get("total_active_aum_usd", 0.0)

    print("\n" + "=" * 80)
    print("SWARM PIPELINE EXECUTION COMPLETE (SUCCESS)")
    print("=" * 80)
    print(f"Duration:                 {result.duration_seconds:.2f} seconds")
    print(f"OpenTelemetry Spans:      {tel.get('total_spans', 0)} total ({tel.get('agent_invocations', 0)} agent spans, {tel.get('tool_invocations', 0)} tool spans)")
    print(f"Active Agents in Swarm:   {', '.join(tel.get('active_agents', []))}")
    print(f"Committed Households:     {len(bundle.households)}")
    print(f"Total Market Value:       ${total_mv:,.2f} USD")
    print(f"Active Billing AUM:       ${active_aum:,.2f} USD (Excludes inactive households)")
    print(f"Committed Accounts:       {len(bundle.accounts)}")
    print(f"Committed Clients:        {len(bundle.clients)}")
    print(f"Committed Interactions:   {len(bundle.interactions)}")
    print(f"Round 2 Clarification Qs: {len(clarifs)} items for Dana Ruiz")
    print(f"Committed Deliverables:   {config.outputs_dir / 'canonical_output.json'}")
    print(f"                          {config.outputs_dir / 'clarifications_round2.md'}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(run_pipeline())
