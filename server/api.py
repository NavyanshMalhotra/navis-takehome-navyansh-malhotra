"""
FastAPI REST API Server for Nevis Agentic Platform.
Exposes endpoints for pipeline triggering, canonical queries, HITL resolution,
OpenTelemetry telemetry traces, and Slack export.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel

from config import config
from pipeline.swarm import NevisSwarmOrchestrator
from pipeline.models import CanonicalOutputBundle, ClarificationItem
from pipeline.auditor import AuditorReflectionAgent
from pipeline.output_generator import ClarificationAgent
from pipeline.agent_tools import knowledge_db
from pipeline.telemetry import telemetry

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nevis Agentic Data Platform API",
    description="REST API for automated wealth management client data onboarding, canonical mapping, and HITL triage.",
    version="2.0.0"
)


class AppState:
    def __init__(self):
        self.orchestrator = NevisSwarmOrchestrator()
        self.bundle: Optional[CanonicalOutputBundle] = None
        self.clarifications: List[ClarificationItem] = []
        self.audit_report = None
        self.is_running = False
        self.resolved_items: Dict[str, Any] = {}

        # Load from existing disk artifacts if available
        canonical_path = config.outputs_dir / "canonical_output.json"
        clarifs_path = config.outputs_dir / "clarifications.json"
        if canonical_path.exists() and clarifs_path.exists():
            try:
                with open(canonical_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.bundle = CanonicalOutputBundle.from_dict(data)
                with open(clarifs_path, "r", encoding="utf-8") as f:
                    c_data = json.load(f)
                self.clarifications = [ClarificationItem(**c) for c in c_data]
                self.audit_report = self.orchestrator.auditor_agent.audit_canonical_bundle(
                    self.bundle, run_semantic_check=False
                )
            except Exception as exc:
                logger.warning("Failed loading cached bundle: %s. Re-running swarm...", exc)
                self.execute_pipeline()
        else:
            self.execute_pipeline()

    def execute_pipeline(self):
        self.is_running = True
        try:
            result = self.orchestrator.run(write_artifacts=True)
            self.bundle = result.bundle
            self.clarifications = result.clarifications
            self.audit_report = result.audit_report

            # Apply any previously resolved HITL items
            for item_id, res in self.resolved_items.items():
                self._apply_resolution_in_memory(item_id, res)
        finally:
            self.is_running = False

    def _apply_resolution_in_memory(self, item_id: str, res: Dict[str, Any]):
        for c in self.clarifications:
            if c.id == item_id:
                c.status = "RESOLVED"
                c.resolved_value = res.get("resolved_value")

        if item_id.startswith("CLARIF-ADV-"):
            hh_slug = item_id.replace("CLARIF-ADV-", "")
            assigned_adv_id = res.get("selected_advisor_id")
            if assigned_adv_id and self.bundle:
                for h in self.bundle.households:
                    if h.household_id == hh_slug:
                        h.primary_advisor_id = assigned_adv_id
                        h._provenance["primary_advisor_id"].method = "HUMAN_HITL_RESOLUTION"
                        h._provenance["primary_advisor_id"].confidence = 1.0
                        h._provenance["primary_advisor_id"].reasoning = f"Manually assigned by operator to {assigned_adv_id}"


state = AppState()


class ResolveClarificationRequest(BaseModel):
    item_id: str
    selected_advisor_id: Optional[str] = None
    resolved_value: Optional[str] = None
    notes: Optional[str] = None


@app.get("/api/pipeline/status")
def get_pipeline_status():
    total_mv = sum(h.market_value_usd for h in state.bundle.households if h.market_value_usd is not None) if state.bundle else 0.0
    active_aum = sum(h.active_aum_usd for h in state.bundle.households if h.active_aum_usd is not None) if state.bundle else 0.0
    return {
        "status": "idle" if not state.is_running else "running",
        "firm_name": config.firm_name,
        "total_households": len(state.bundle.households) if state.bundle else 0,
        "total_clients": len(state.bundle.clients) if state.bundle else 0,
        "total_accounts": len(state.bundle.accounts) if state.bundle else 0,
        "total_advisors": len(state.bundle.advisors) if state.bundle else 0,
        "total_interactions": len(state.bundle.interactions) if state.bundle else 0,
        "total_clarifications": len([c for c in state.clarifications if c.id not in state.resolved_items]),
        "total_resolved": len(state.resolved_items),
        "total_market_value_usd": total_mv,
        "active_aum_usd": active_aum,
        "audit_passed": state.audit_report.is_valid if state.audit_report else False,
    }


@app.post("/api/pipeline/run")
def trigger_pipeline(background_tasks: BackgroundTasks):
    if state.is_running:
        return {"status": "already_running"}
    state.execute_pipeline()
    return {"status": "success", "message": "Google ADK swarm execution completed."}


@app.get("/api/canonical")
def get_canonical_book(entity_type: Optional[str] = None, search: Optional[str] = None):
    if not state.bundle:
        raise HTTPException(status_code=404, detail="Canonical bundle not initialized.")
    data = state.bundle.to_dict()
    if entity_type and entity_type in data:
        items = data[entity_type]
        if search:
            s = search.lower()
            items = [i for i in items if s in json.dumps(i).lower()]
        return {entity_type: items}
    return data


@app.get("/api/clarifications")
def get_clarifications():
    return {
        "pending": [c.to_dict() for c in state.clarifications if c.id not in state.resolved_items],
        "resolved": [c.to_dict() for c in state.clarifications if c.id in state.resolved_items],
    }


@app.post("/api/clarifications/resolve")
def resolve_clarification(req: ResolveClarificationRequest):
    found = any(c.id == req.item_id for c in state.clarifications)
    if not found:
        raise HTTPException(status_code=404, detail=f"Clarification item '{req.item_id}' not found.")

    payload = req.model_dump()
    state.resolved_items[req.item_id] = payload
    state._apply_resolution_in_memory(req.item_id, payload)

    # Persist resolution to SQLite knowledge store
    knowledge_db.save_rule(
        rule_id=f"HITL-{req.item_id}",
        category="HITL_RESOLUTION",
        description=f"Operator resolved {req.item_id}: {req.resolved_value or req.selected_advisor_id}",
        stakeholder="Operator (HITL)",
        source_reference="POST /api/clarifications/resolve",
        scope="CLIENT_SPECIFIC",
        metadata=payload,
    )

    if state.bundle:
        state.audit_report = state.orchestrator.auditor_agent.audit_canonical_bundle(state.bundle)
        ClarificationAgent.write_canonical_json(state.bundle, config.outputs_dir / "canonical_output.json")
        ClarificationAgent.write_clarifications_markdown(
            [c for c in state.clarifications if c.id not in state.resolved_items],
            config.outputs_dir / "clarifications_round2.md"
        )

    return {
        "status": "success",
        "item_id": req.item_id,
        "message": "Item resolved and canonical book updated.",
        "remaining_clarifications": len([c for c in state.clarifications if c.id not in state.resolved_items]),
    }


@app.get("/api/rules")
def get_rules():
    return {"rules": state.orchestrator.knowledge_agent.get_all_rules()}


@app.get("/api/audit")
def get_audit_report():
    if not state.audit_report:
        raise HTTPException(status_code=404, detail="Audit report not found.")
    return {
        "is_valid": state.audit_report.is_valid,
        "rules_checked": state.audit_report.rules_checked,
        "rules_passed": state.audit_report.rules_passed,
        "rules_failed": state.audit_report.rules_failed,
        "rule_results": state.audit_report.rule_results,
        "errors": state.audit_report.errors,
        "warnings": state.audit_report.warnings,
        "summary": state.audit_report.summary(),
    }


@app.get("/api/telemetry/traces")
def get_telemetry_traces():
    """Returns OpenTelemetry recorded spans and execution metrics."""
    return {
        "summary": telemetry.get_summary(),
        "traces": telemetry.get_traces(),
    }


@app.get("/api/export/slack")
def export_slack_markdown():
    clarif_path = config.outputs_dir / "clarifications_round2.md"
    if clarif_path.exists():
        return PlainTextResponse(clarif_path.read_text(encoding="utf-8"))
    return PlainTextResponse("Clarification export not found.")


STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Nevis Agentic Platform API Ready</h1><p>Visit /docs for Swagger UI.</p>")
