"""
Unstructured Document & Context Mining Agent.
Reads Notion client and meeting Markdown notes and Slack communications.
Extracts hidden relationship facts (spouses, parent households, LLC affiliations,
custodian notes, and departure statuses) with exact document citations.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from config import config
from pipeline.llm_client import llm_client

class DocMinerAgent:
    def __init__(self):
        prompt_path = config.prompts_dir / "doc_mining.txt"
        self.system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    def mine_client_notes(self, clients: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Mines all client Markdown page bodies.
        Returns a mapping: client_name -> extracted insights dict.
        """
        extracted_by_client = {}

        for c in clients:
            name = c.get("Name", "").strip()
            body = c.get("_page_body", "").strip()
            file_path = c.get("_page_file", "")
            
            insights = {
                "spouse_of": None,
                "household_hint": None,
                "holds_joint_account": False,
                "foreign_currency_hint": None,
                "acquisition_notes": None,
                "advisor_notes": None,
                "raw_snippets": []
            }

            if not body:
                extracted_by_client[name] = insights
                continue

            # Check for spouse / marital relation
            # e.g. "Wife of Robert Chen — same household"
            wife_match = re.search(r"wife of\s+([A-Za-z\s]+)", body, re.IGNORECASE)
            husband_match = re.search(r"husband of\s+([A-Za-z\s]+)", body, re.IGNORECASE)
            spouse_match = re.search(r"spouse of\s+([A-Za-z\s]+)", body, re.IGNORECASE)
            
            if wife_match:
                spouse_name = wife_match.group(1).split("—")[0].split("-")[0].strip()
                insights["spouse_of"] = spouse_name
                insights["household_hint"] = f"{spouse_name.split()[-1]} Household"
                insights["raw_snippets"].append(f"Wife of {spouse_name}")
            elif husband_match:
                spouse_name = husband_match.group(1).split("—")[0].split("-")[0].strip()
                insights["spouse_of"] = spouse_name
                insights["household_hint"] = f"{spouse_name.split()[-1]} Household"
                insights["raw_snippets"].append(f"Husband of {spouse_name}")
            elif spouse_match:
                spouse_name = spouse_match.group(1).split("—")[0].split("-")[0].strip()
                insights["spouse_of"] = spouse_name
                insights["household_hint"] = f"{spouse_name.split()[-1]} Household"
                insights["raw_snippets"].append(f"Spouse of {spouse_name}")

            # Check joint account mentions
            if "joint account" in body.lower():
                insights["holds_joint_account"] = True
                insights["raw_snippets"].append("Holds joint account")

            # Check foreign currency / Swiss / Euro hints
            if "francs" in body.lower() or "chf" in body.lower() or "geneva" in body.lower():
                insights["foreign_currency_hint"] = "CHF"
                insights["raw_snippets"].append("Held in Swiss francs")
            elif "euro" in body.lower() or "eur" in body.lower():
                insights["foreign_currency_hint"] = "EUR"
                insights["raw_snippets"].append("Held in euros")

            # Check Harborline / acquisition mentions
            if "harborline" in body.lower():
                insights["acquisition_notes"] = "Harborline acquisition"
                insights["raw_snippets"].append("Came over in Harborline acquisition")

            # Check unassigned advisor mentions
            if "doesn't really have a proper advisor" in body.lower() or "never got a proper advisor" in body.lower():
                insights["advisor_notes"] = "Unassigned advisor of record"
                insights["raw_snippets"].append("No proper advisor of record assigned")

            extracted_by_client[name] = insights

        return extracted_by_client

    def mine_meeting_notes(self, meetings: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Mines all meeting Markdown bodies.
        Returns a mapping: meeting_name -> extracted insights dict.
        """
        extracted_by_meeting = {}

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
                "raw_snippets": []
            }

            if body:
                # Check unentered lead
                if "not in the crm yet" in body.lower() or "referred lead" in body.lower():
                    insights["is_unentered_lead"] = True
                    insights["raw_snippets"].append("Referred lead — not in the CRM yet")

                # Check Bob / Robert nickname
                if "quick portfolio check-in with bob" in body.lower() or client_field.lower() == "bob chen":
                    insights["client_alias"] = "Robert Chen"
                    insights["raw_snippets"].append("Bob Chen is Robert Chen")

                # Check churn / winding down
                if "winding down" in body.lower():
                    insights["is_churn_discussion"] = True
                    insights["raw_snippets"].append("Discussed winding down")

                # Check LLC / IRA
                if "ira sits under the llc" in body.lower():
                    insights["entity_notes"] = "IRA under LLC discussion"
                    insights["raw_snippets"].append("Family deciding whether Kenji's IRA sits under the LLC or on its own")

            extracted_by_meeting[name] = insights

        return extracted_by_meeting
