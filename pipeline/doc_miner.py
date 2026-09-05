"""
Document & Context Mining Agent.
Reads Notion client dossiers and meeting notes to extract latent relationship facts
(spouses, parent households, corporate signer roles, custodian currency hints,
and operational flags) using Google Gemini and exact source citations.
"""

import logging
from typing import Dict, List, Any, Optional
from config import config
from pipeline.llm_client import llm_client

logger = logging.getLogger(__name__)


class DocMinerAgent:
    def __init__(self):
        prompt_path = config.prompts_dir / "doc_mining.txt"
        self.system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    def mine_client_notes(self, clients: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Mines all client Markdown page bodies using Google Gemini for unstructured reasoning.
        Returns a mapping: client_name -> extracted insights dict.
        """
        extracted_by_client: Dict[str, Dict[str, Any]] = {}
        notes_to_mine: List[Dict[str, str]] = []

        # Prepare default empty insight structure for all clients
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
            extracted_by_client[name] = insights

            if body:
                notes_to_mine.append({
                    "name": name,
                    "body": body,
                    "file": file_path,
                })

        if not notes_to_mine:
            return extracted_by_client

        # Batch all non-empty client notes into a single structured LLM reasoning call
        batch_prompt = (
            "Analyze the following client CRM dossier notes. For each client, extract:\n"
            "- spouse_of: Full name of spouse if indicated (e.g. 'Robert Chen', 'Sarah Thompson')\n"
            "- role: Canonical role if implied ('PRIMARY', 'SPOUSE', 'SIGNER', 'TRUSTEE', 'DEPENDENT')\n"
            "- household_hint: Likely household name if specified\n"
            "- holds_joint_account: boolean (true if notes mention holding a joint account)\n"
            "- foreign_currency_hint: Currency code if foreign holdings mentioned ('EUR', 'CHF')\n"
            "- acquisition_notes: Mentions of Harborline or legacy acquisition\n"
            "- advisor_notes: Notes indicating unassigned advisor of record\n"
            "- affiliated_entities: List of legal entities or LLCs (e.g. ['Nakamura Holdings LLC'])\n"
            "- ops_flag: Any operational warning or note flagged for ops\n"
            "- raw_snippets: List of exact quoted sentences/clauses supporting the extractions\n\n"
            "Input Client Notes:\n"
        )
        for item in notes_to_mine:
            batch_prompt += f"\n--- Client: {item['name']} (File: {item['file']}) ---\n{item['body']}\n"

        batch_prompt += (
            "\nOutput a JSON object with key 'clients' mapping client names to their extracted insight dictionary."
        )

        try:
            logger.info("Calling Gemini to mine %d client dossier notes...", len(notes_to_mine))
            resp = llm_client.generate_json(self.system_prompt, batch_prompt)
            llm_results = resp.get("clients", {})

            for name, insights_data in llm_results.items():
                # Match by exact or partial name
                target_key = next((k for k in extracted_by_client if k.lower() == name.lower()), None)
                if not target_key:
                    target_key = next((k for k in extracted_by_client if name.lower() in k.lower() or k.lower() in name.lower()), None)

                def _clean_val(val: Any) -> Any:
                    if isinstance(val, dict):
                        return val.get("value", "")
                    if isinstance(val, list):
                        return [_clean_val(item) for item in val]
                    return val

                if target_key:
                    base = extracted_by_client[target_key]
                    if insights_data.get("spouse_of"):
                        base["spouse_of"] = _clean_val(insights_data["spouse_of"])
                    if insights_data.get("role"):
                        base["role"] = str(_clean_val(insights_data["role"])).upper()
                    if insights_data.get("household_hint"):
                        base["household_hint"] = _clean_val(insights_data["household_hint"])
                    if insights_data.get("holds_joint_account") is not None:
                        base["holds_joint_account"] = bool(_clean_val(insights_data["holds_joint_account"]))
                    if insights_data.get("foreign_currency_hint"):
                        base["foreign_currency_hint"] = _clean_val(insights_data["foreign_currency_hint"])
                    if insights_data.get("acquisition_notes"):
                        base["acquisition_notes"] = _clean_val(insights_data["acquisition_notes"])
                    if insights_data.get("advisor_notes"):
                        base["advisor_notes"] = _clean_val(insights_data["advisor_notes"])
                    if insights_data.get("affiliated_entities"):
                        entities = _clean_val(insights_data["affiliated_entities"])
                        base["affiliated_entities"] = [e for e in entities if e] if isinstance(entities, list) else [entities]
                    if insights_data.get("ops_flag"):
                        base["ops_flag"] = _clean_val(insights_data["ops_flag"])
                    if insights_data.get("raw_snippets"):
                        snippets = _clean_val(insights_data["raw_snippets"])
                        base["raw_snippets"] = [s for s in snippets if s] if isinstance(snippets, list) else [snippets]

        except Exception as e:
            logger.error("LLM client note mining failed: %s", e)
            raise

        return extracted_by_client

    def mine_meeting_notes(self, meetings: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Mines all meeting Markdown bodies using Google Gemini.
        Returns a mapping: meeting_name -> extracted insights dict.
        """
        extracted_by_meeting: Dict[str, Dict[str, Any]] = {}
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
            extracted_by_meeting[name] = insights

            if body:
                meetings_to_mine.append({
                    "name": name,
                    "client_field": client_field,
                    "body": body,
                })

        if not meetings_to_mine:
            return extracted_by_meeting

        batch_prompt = (
            "Analyze the following meeting notes from an RIA CRM. For each meeting, extract:\n"
            "- client_alias: Canonical client name if the meeting uses a diminutive/nickname (e.g. 'Bob Chen' -> 'Robert Chen')\n"
            "- is_unentered_lead: boolean (true if meeting is with a prospective client not yet in CRM)\n"
            "- is_churn_discussion: boolean (true if discussion involves winding down or churn)\n"
            "- entity_notes: Notes on legal entity structuring (e.g. family IRA under LLC)\n"
            "- raw_snippets: List of exact quoted sentences supporting the extractions\n\n"
            "Input Meetings:\n"
        )
        for item in meetings_to_mine:
            batch_prompt += f"\n--- Meeting: {item['name']} (Client Field: {item['client_field']}) ---\n{item['body']}\n"

        batch_prompt += "\nOutput a JSON object with key 'meetings' mapping meeting names to their extracted insights."

        try:
            logger.info("Calling Gemini to mine %d meeting notes...", len(meetings_to_mine))
            resp = llm_client.generate_json(self.system_prompt, batch_prompt)
            llm_results = resp.get("meetings", {})

            for name, insights_data in llm_results.items():
                target_key = next((k for k in extracted_by_meeting if k.lower() == name.lower()), None)
                if not target_key:
                    target_key = next((k for k in extracted_by_meeting if name.lower() in k.lower() or k.lower() in name.lower()), None)

                def _clean_val(val: Any) -> Any:
                    if isinstance(val, dict):
                        return val.get("value") or val.get("snippet", "")
                    if isinstance(val, list):
                        return [_clean_val(item) for item in val]
                    return val

                if target_key:
                    base = extracted_by_meeting[target_key]
                    if insights_data.get("client_alias"):
                        base["client_alias"] = _clean_val(insights_data["client_alias"])
                    if insights_data.get("is_unentered_lead") is not None:
                        base["is_unentered_lead"] = bool(_clean_val(insights_data["is_unentered_lead"]))
                    if insights_data.get("is_churn_discussion") is not None:
                        base["is_churn_discussion"] = bool(_clean_val(insights_data["is_churn_discussion"]))
                    if insights_data.get("entity_notes"):
                        base["entity_notes"] = _clean_val(insights_data["entity_notes"])
                    if insights_data.get("raw_snippets"):
                        snippets = _clean_val(insights_data["raw_snippets"])
                        base["raw_snippets"] = [s for s in snippets if s] if isinstance(snippets, list) else [snippets]

        except Exception as e:
            logger.error("LLM meeting note mining failed: %s", e)
            raise

        return extracted_by_meeting
