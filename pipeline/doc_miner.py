"""
Dossier & Document Mining Agent.
Extracts latent relationship facts from Notion client and meeting notes
(spousal ties, corporate signer roles, currency hints, and churn indicators)
using Google GenAI models with field-level citations and telemetry tracking.
"""

import logging
from typing import Dict, List, Any, Optional

from google.adk.agents import BaseAgent
from config import config
from pipeline.llm_client import llm_client
from pipeline.telemetry import telemetry

logger = logging.getLogger(__name__)


class DossierMinerAgent(BaseAgent):
    """Google ADK agent for mining unstructured CRM dossiers and meeting markdown notes."""

    name: str = "DossierMinerAgent"
    description: str = "Mines unstructured client dossiers and meeting notes for latent facts and relationships."

    def __init__(self, **data):
        super().__init__(**data)
        prompt_path = config.prompts_dir / "doc_mining.txt"
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
        object.__setattr__(self, "system_prompt", system_prompt)

    def mine_client_notes(self, clients: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Mines client notes for relationships, roles, and entities."""
        with telemetry.trace_agent(self.name, task="mine_client_notes"):
            extracted: Dict[str, Dict[str, Any]] = {}
            notes_to_mine: List[Dict[str, str]] = []

            for c in clients:
                name = c.get("Name", "").strip()
                body = c.get("_page_body", "").strip()
                file_path = c.get("_page_file", "")

                insights = {
                    "spouse_of": None,
                    "role": "PRIMARY",
                    "household_hint": None,
                    "holds_joint_account": False,
                    "foreign_currency_hint": None,
                    "acquisition_notes": None,
                    "advisor_notes": None,
                    "affiliated_entities": [],
                    "ops_flag": None,
                    "raw_snippets": [],
                    "source_file": file_path,
                }
                extracted[name] = insights
                if body:
                    notes_to_mine.append({"name": name, "body": body, "file": file_path})

            if not notes_to_mine or not llm_client.is_available:
                return extracted

            batch_size = 5
            for i in range(0, len(notes_to_mine), batch_size):
                chunk = notes_to_mine[i : i + batch_size]
                batch_prompt = (
                    "For each client CRM dossier below, extract structured insights into JSON strictly matching this schema:\n"
                    "{\n"
                    "  \"clients\": {\n"
                    "    \"<Exact Client Name>\": {\n"
                    "      \"spouse_of\": null or \"Full Name of Spouse\",\n"
                    "      \"role\": \"PRIMARY\" or \"SPOUSE\" or \"SIGNER\" or \"DEPENDENT\",\n"
                    "      \"household_hint\": null or \"Household Name\",\n"
                    "      \"holds_joint_account\": true or false,\n"
                    "      \"foreign_currency_hint\": null or \"Currency Code\",\n"
                    "      \"acquisition_notes\": null or \"Notes\",\n"
                    "      \"advisor_notes\": null or \"Notes\",\n"
                    "      \"affiliated_entities\": [],\n"
                    "      \"ops_flag\": null or \"Warning\",\n"
                    "      \"raw_snippets\": [\"exact quotes\"]\n"
                    "    }\n"
                    "  }\n"
                    "}\n\n"
                    "Input Client Notes:\n"
                )
                for item in chunk:
                    batch_prompt += f"\n--- Client: {item['name']} (File: {item['file']}) ---\n{item['body']}\n"
                batch_prompt += "\nOutput valid JSON only."

                try:
                    with telemetry.trace_tool("llm_mine_client_batch", batch_index=(i // batch_size) + 1):
                        resp = llm_client.generate_json(self.system_prompt, batch_prompt)
                    results = resp.get("clients", {})

                    for name, data in results.items():
                        target = next((k for k in extracted if k.lower() == name.lower()), None)
                        if not target:
                            target = next((k for k in extracted if name.lower() in k.lower() or k.lower() in name.lower()), None)

                        def _clean_val(val: Any) -> Any:
                            if isinstance(val, dict):
                                return val.get("value", "")
                            if isinstance(val, list):
                                return [_clean_val(x) for x in val]
                            return val

                        if target:
                            base = extracted[target]
                            if data.get("spouse_of"):
                                base["spouse_of"] = _clean_val(data["spouse_of"])
                            if data.get("role"):
                                base["role"] = str(_clean_val(data["role"])).upper()
                            if data.get("household_hint"):
                                base["household_hint"] = _clean_val(data["household_hint"])
                            if data.get("holds_joint_account") is not None:
                                base["holds_joint_account"] = bool(_clean_val(data["holds_joint_account"]))
                            if data.get("foreign_currency_hint"):
                                base["foreign_currency_hint"] = _clean_val(data["foreign_currency_hint"])
                            if data.get("acquisition_notes"):
                                base["acquisition_notes"] = _clean_val(data["acquisition_notes"])
                            if data.get("advisor_notes"):
                                base["advisor_notes"] = _clean_val(data["advisor_notes"])
                            if data.get("affiliated_entities"):
                                ents = _clean_val(data["affiliated_entities"])
                                base["affiliated_entities"] = [e for e in ents if e] if isinstance(ents, list) else [ents]
                            if data.get("ops_flag"):
                                base["ops_flag"] = _clean_val(data["ops_flag"])
                            if data.get("raw_snippets"):
                                snips = _clean_val(data["raw_snippets"])
                                base["raw_snippets"] = [s for s in snips if s] if isinstance(snips, list) else [snips]
                except Exception as exc:
                    logger.warning("Client note batch %d mining failed: %s", (i // batch_size) + 1, exc)

            return extracted

    def mine_meeting_notes(self, meetings: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Mines meeting notes for client aliases, prospect leads, and discussion topics."""
        with telemetry.trace_agent(self.name, task="mine_meeting_notes"):
            extracted: Dict[str, Dict[str, Any]] = {}
            meetings_to_mine: List[Dict[str, str]] = []

            for m in meetings:
                name = m.get("Name", "").strip()
                body = m.get("_page_body", "").strip()
                client_field = m.get("Client", "").strip()

                insights = {
                    "client_alias": None,
                    "is_unentered_lead": False,
                    "is_churn_discussion": False,
                    "entity_notes": None,
                    "summary": body if body else None,
                    "raw_snippets": [],
                }
                extracted[name] = insights
                if body:
                    meetings_to_mine.append({"name": name, "client_field": client_field, "body": body})

            if not meetings_to_mine or not llm_client.is_available:
                return extracted

            batch_prompt = (
                "For each meeting note below, extract structured insights into JSON strictly matching this schema:\n"
                "{\n"
                "  \"meetings\": {\n"
                "    \"<Exact Meeting Name>\": {\n"
                "      \"client_alias\": null or \"Canonical Client Name\",\n"
                "      \"is_unentered_lead\": true or false,\n"
                "      \"is_churn_discussion\": true or false,\n"
                "      \"entity_notes\": null or \"Notes\",\n"
                "      \"raw_snippets\": [\"exact quotes\"]\n"
                "    }\n"
                "  }\n"
                "}\n\n"
                "Input Meetings:\n"
            )
            for item in meetings_to_mine:
                batch_prompt += f"\n--- Meeting: {item['name']} (Client: {item['client_field']}) ---\n{item['body']}\n"
            batch_prompt += "\nOutput valid JSON only."

            try:
                with telemetry.trace_tool("llm_mine_meeting_notes", count=len(meetings_to_mine)):
                    resp = llm_client.generate_json(self.system_prompt, batch_prompt)
                results = resp.get("meetings", {})

                for name, data in results.items():
                    target = next((k for k in extracted if k.lower() == name.lower()), None)
                    if not target:
                        target = next((k for k in extracted if name.lower() in k.lower() or k.lower() in name.lower()), None)

                    def _clean_val(val: Any) -> Any:
                        if isinstance(val, dict):
                            return val.get("value") or val.get("snippet", "")
                        if isinstance(val, list):
                            return [_clean_val(x) for x in val]
                        return val

                    if target:
                        base = extracted[target]
                        if data.get("client_alias"):
                            base["client_alias"] = _clean_val(data["client_alias"])
                        if data.get("is_unentered_lead") is not None:
                            base["is_unentered_lead"] = bool(_clean_val(data["is_unentered_lead"]))
                        if data.get("is_churn_discussion") is not None:
                            base["is_churn_discussion"] = bool(_clean_val(data["is_churn_discussion"]))
                        if data.get("entity_notes"):
                            base["entity_notes"] = _clean_val(data["entity_notes"])
                        if data.get("raw_snippets"):
                            snips = _clean_val(data["raw_snippets"])
                            base["raw_snippets"] = [s for s in snips if s] if isinstance(snips, list) else [snips]
            except Exception as exc:
                logger.warning("Meeting notes mining failed gracefully: %s. Using default summaries.", exc)

            return extracted


# Backward compatibility alias
DocMinerAgent = DossierMinerAgent
