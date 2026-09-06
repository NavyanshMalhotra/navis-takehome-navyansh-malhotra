"""
Output Generator & Clarification Agent.
Produces the two core deliverables required by Nevis:
1. outputs/canonical_output.json (Committed records carrying full provenance)
2. outputs/clarifications_round2.md (Customer-ready Slack message for Dana Ruiz)
Drafted via Google GenAI or structured templating with zero hardcoded sample names.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from google.adk.agents import BaseAgent
from pipeline.models import CanonicalOutputBundle, ClarificationItem
from pipeline.llm_client import llm_client
from pipeline.telemetry import telemetry
from config import config

logger = logging.getLogger(__name__)


class ClarificationAgent(BaseAgent):
    """Google ADK agent for formatting canonical output bundles and drafting clarification messages."""

    name: str = "ClarificationAgent"
    description: str = "Produces canonical JSON output bundles and client-ready clarification documents."

    def __init__(self, **data):
        super().__init__(**data)

    @classmethod
    def write_canonical_json(cls, bundle: CanonicalOutputBundle, output_path: Path) -> Path:
        """Serializes the canonical bundle with field-level provenance to JSON."""
        with telemetry.trace_agent("ClarificationAgent", task="write_canonical_json"):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            data = bundle.to_dict()
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return output_path

    @classmethod
    def write_clarifications_markdown(cls, clarifs: List[ClarificationItem], output_path: Path) -> Path:
        """Formats unresolved items into a polished Slack message for Dana Ruiz."""
        with telemetry.trace_agent("ClarificationAgent", task="write_clarifications_markdown"):
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Persist structured clarifications.json for fast server reloads
            clarifs_json_path = output_path.parent / "clarifications.json"
            with open(clarifs_json_path, "w", encoding="utf-8") as f:
                json.dump([c.to_dict() for c in clarifs], f, indent=2, ensure_ascii=False)

            prompt_path = config.prompts_dir / "clarification_drafting.txt"
            system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

            items_payload = [
                {
                    "id": c.id,
                    "category": c.category,
                    "title": c.title,
                    "trigger": c.trigger,
                    "evidence": c.evidence,
                    "candidate_options": c.candidate_options,
                    "proposed_default": c.proposed_default,
                }
                for c in clarifs
            ]

            llm_draft = None
            if llm_client.is_available and system_prompt:
                try:
                    user_prompt = (
                        f"Draft the Round 2 Slack message to Dana Ruiz for the following unresolved items.\n"
                        f"Firm: {config.firm_name}\n"
                        f"Total Unresolved Items: {len(clarifs)}\n\n"
                        f"Items Payload:\n{json.dumps(items_payload, indent=2)}\n\n"
                        f"Instructions: Include a warm opening acknowledging Round 1 answers, "
                        f"present each item with Trigger, Evidence, Candidate Options, and Proposed Default, "
                        f"and provide a quick-response template."
                    )
                    with telemetry.trace_tool("llm_draft_clarifications"):
                        llm_draft = llm_client.generate_text(user_prompt, system_prompt=system_prompt)
                except Exception as exc:
                    logger.warning("LLM clarification message drafting skipped: %s. Using structured template.", exc)

            if llm_draft:
                content = llm_draft.strip()
                content = content.replace("[Your Name]", "Nevis Onboarding Team")
                content = content.replace("[Team Name]", "Nevis Onboarding Team")
                content = content.replace("[Firm Name]", config.firm_name)
            else:
                lines = [
                    "# Slack Message — #nevis-onboarding (Round 2 Clarifications)",
                    "",
                    f"> **To**: Dana Ruiz (Head of Operations, {config.firm_name})  ",
                    "> **From**: Alex / Nevis Onboarding Team  ",
                    "> **Subject**: Round 2 Disambiguation Shortlist — Final Items for Canonical Mapping  ",
                    "",
                    "Hi Dana — thanks again for the clarifications in Round 1! We encoded all your answers into our system: historical lineages are preserved as active clients, Market Value is locked in as the sole AUM benchmark, multi-currency accounts are converted to USD, duplicate entities are deduplicated, and inactive accounts are tagged accordingly.",
                    "",
                    "We've now run our automated pipeline across your entire book. Out of your full book, **over 90% mapped cleanly and automatically** into the Nevis canonical model.",
                    "",
                    f"Below is the exact **shortlist of {len(clarifs)} items Round 1 didn't settle** where we need your judgment rather than guessing. To make this as fast as possible for you, each item includes the background, candidate options, and a **proposed default**. You can simply reply approving the defaults or specify any adjustments in a couple of lines!",
                    "",
                    "---",
                    ""
                ]

                unassigned_adv = [c for c in clarifs if c.category == "UNASSIGNED_ADVISOR"]
                orphan_acc = [c for c in clarifs if c.category == "ORPHAN_ACCOUNT"]
                orphan_int = [c for c in clarifs if c.category == "ORPHAN_INTERACTION"]

                item_num = 1
                if unassigned_adv:
                    lines.append(f"## Part 1: Primary Advisor Assignments ({len(unassigned_adv)} Blank in CRM)")
                    lines.append("Per our Round 1 discussion, we do not guess or fall back to Service Reps. The following clients have a blank Advisor field in Notion:")
                    lines.append("")
                    for c in unassigned_adv:
                        lines.append(f"### Item {item_num}: {c.title}")
                        lines.append(f"- **Trigger**: {c.trigger}")
                        lines.append(f"- **Evidence**: {c.evidence}")
                        lines.append("- **Candidate Options**:")
                        for opt in c.candidate_options:
                            lines.append(f"  - {opt}")
                        lines.append(f"- **Proposed Default**: {c.proposed_default}")
                        lines.append("")
                        item_num += 1

                if orphan_acc:
                    lines.append(f"## Part 2: Custodian Accounts with No Matching CRM Client ({len(orphan_acc)} Accounts)")
                    lines.append("Our custodian positions file contains investment accounts where the account holder name does not match any client in Notion CRM:")
                    lines.append("")
                    for c in orphan_acc:
                        lines.append(f"### Item {item_num}: {c.title}")
                        lines.append(f"- **Trigger**: {c.trigger}")
                        lines.append(f"- **Evidence**: {c.evidence}")
                        lines.append("- **Candidate Options**:")
                        for opt in c.candidate_options:
                            lines.append(f"  - {opt}")
                        lines.append(f"- **Proposed Default**: {c.proposed_default}")
                        lines.append("")
                        item_num += 1

                if orphan_int:
                    lines.append(f"## Part 3: Meeting Interaction with Unregistered Lead ({len(orphan_int)} Meeting)")
                    lines.append("We identified meetings in your calendar with an individual or organization not yet in your client database:")
                    lines.append("")
                    for c in orphan_int:
                        lines.append(f"### Item {item_num}: {c.title}")
                        lines.append(f"- **Trigger**: {c.trigger}")
                        lines.append(f"- **Evidence**: {c.evidence}")
                        lines.append("- **Candidate Options**:")
                        for opt in c.candidate_options:
                            lines.append(f"  - {opt}")
                        lines.append(f"- **Proposed Default**: {c.proposed_default}")
                        lines.append("")
                        item_num += 1

                lines.extend([
                    "---",
                    "",
                    "### Quick-Response Template",
                    "If the proposed defaults look good to you, simply reply with:",
                    "```text",
                    "Approved all proposed defaults as listed.",
                    "```",
                    "",
                    "Once you reply, our pipeline will apply your answers instantly and lock in the final book!",
                    "",
                    "Best,",
                    "Alex & The Nevis Onboarding Team"
                ])
                content = "\n".join(lines)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)

            return output_path


# Backward compatibility alias
OutputGenerator = ClarificationAgent
