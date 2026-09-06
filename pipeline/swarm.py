"""
Google ADK Multi-Agent Swarm Orchestrator for Nevis Platform.
Coordinates specialized agents across ingestion, knowledge mining, entity resolution,
canonical mapping, reflective auditing, and clarification synthesis with OpenTelemetry tracing.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple

from google.adk.agents import BaseAgent
from config import config
from pipeline.validator import SourceValidationSuite, SourceValidationReport
from pipeline.knowledge_layer import KnowledgeMiningAgent
from pipeline.doc_miner import DossierMinerAgent
from pipeline.entity_resolver import EntityResolverAgent
from pipeline.transformer import CanonicalTransformerAgent
from pipeline.auditor import AuditorReflectionAgent, AuditReport
from pipeline.output_generator import ClarificationAgent
from pipeline.models import CanonicalOutputBundle, ClarificationItem
from pipeline.readers import (
    read_advisor_roster,
    read_custodian_positions,
    read_notion_clients,
    read_notion_meetings,
    read_slack_thread,
)
from pipeline.telemetry import telemetry

logger = logging.getLogger(__name__)


@dataclass
class SwarmExecutionResult:
    bundle: CanonicalOutputBundle
    clarifications: List[ClarificationItem]
    audit_report: AuditReport
    validation_report: SourceValidationReport
    telemetry_summary: Dict[str, Any]
    duration_seconds: float


class NevisSwarmOrchestrator(BaseAgent):
    """Orchestrates the swarm of Google ADK agents for wealth data onboarding."""

    name: str = "NevisSwarmOrchestrator"
    description: str = "Coordinates multi-agent ingestion, disambiguation, mapping, audit, and output synthesis."

    def __init__(self, **data):
        super().__init__(**data)
        object.__setattr__(self, "knowledge_agent", KnowledgeMiningAgent())
        object.__setattr__(self, "dossier_agent", DossierMinerAgent())
        object.__setattr__(self, "resolver_agent", EntityResolverAgent())
        object.__setattr__(self, "transformer_agent", CanonicalTransformerAgent(self.knowledge_agent))
        object.__setattr__(self, "auditor_agent", AuditorReflectionAgent())
        object.__setattr__(self, "clarification_agent", ClarificationAgent())

    def run(self, write_artifacts: bool = True) -> SwarmExecutionResult:
        """Executes the full agentic swarm workflow with OpenTelemetry instrumentation."""
        start_time = time.time()
        telemetry.reset()

        with telemetry.trace_agent(self.name, task="swarm_pipeline_run"):
            # 1. Ingestion Phase
            advisors = read_advisor_roster(config.sources_dir / "advisor_roster.csv")
            custodian = read_custodian_positions(config.sources_dir / "custodian_positions.xlsx")
            clients = read_notion_clients(config.sources_dir / "notion_export")
            meetings = read_notion_meetings(config.sources_dir / "notion_export")
            read_slack_thread(config.sources_dir / "ops_slack_thread.md")

            # 2. Pre-flight Validation
            val_report = SourceValidationSuite.audit_sources(advisors, clients, meetings, custodian)
            if not val_report.is_valid:
                raise ValueError(f"Source validation failed: {val_report.errors}")

            # 3. Knowledge Layer Initialization
            self.knowledge_agent.load_rules()

            # 4. Canonical Transformation
            bundle, raw_clarifs = self.transformer_agent.transform_all(
                advisors, clients, meetings, custodian
            )

            # 5. Reflective Integrity Audit
            audit_report, bundle, clarifs = self.auditor_agent.audit_and_reflect(
                bundle, raw_clarifs, run_semantic_check=True
            )

            # 6. Artifact Synthesis
            if write_artifacts:
                self.clarification_agent.write_canonical_json(
                    bundle, config.outputs_dir / "canonical_output.json"
                )
                self.clarification_agent.write_clarifications_markdown(
                    clarifs, config.outputs_dir / "clarifications_round2.md"
                )
                try:
                    import json
                    with open(config.outputs_dir / "telemetry_traces.json", "w", encoding="utf-8") as tf:
                        json.dump(telemetry.get_traces(), tf, indent=2)
                except Exception as exc:
                    logger.debug("Failed saving telemetry traces: %s", exc)

            duration = time.time() - start_time
            telemetry_summary = telemetry.get_summary()

            return SwarmExecutionResult(
                bundle=bundle,
                clarifications=clarifs,
                audit_report=audit_report,
                validation_report=val_report,
                telemetry_summary=telemetry_summary,
                duration_seconds=duration,
            )
