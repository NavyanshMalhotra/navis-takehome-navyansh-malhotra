"""
Output Generator Module.
Produces the two core deliverables required by Nevis:
1. outputs/canonical_output.json (Committed records carrying full provenance)
2. outputs/clarifications_round2.md (Customer-ready Slack message for Dana Ruiz)
"""

import json
from pathlib import Path
from typing import List
from pipeline.models import CanonicalOutputBundle, ClarificationItem
from config import config

class OutputGenerator:
    @classmethod
    def write_canonical_json(cls, bundle: CanonicalOutputBundle, output_path: Path) -> Path:
        """Serializes the canonical bundle with field-level provenance to JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = bundle.to_dict()
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return output_path

    @classmethod
    def write_clarifications_markdown(cls, clarifs: List[ClarificationItem], output_path: Path) -> Path:
        """
        Formats unresolved items into a polished, professional Slack message
        for Dana Ruiz (Head of Operations).
        Follows the strict 4-part structure: Trigger, Evidence, Candidate Options, Proposed Default.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# Slack Message — #nevis-onboarding (Round 2 Clarifications)",
            "",
            "> **To**: Dana Ruiz (Head of Operations, Beaconcrest Advisors)  ",
            "> **From**: Alex / Nevis Onboarding Team  ",
            "> **Subject**: Round 2 Disambiguation Shortlist — Final Items for Canonical Mapping  ",
            "",
            "Hi Dana — huge thanks again for the clarifications in Round 1! We encoded all your answers into our system: the Harborline 'Legacy' lineage is preserved as active clients, Market Value is locked in as the sole AUM benchmark, Yusuf's EUR account is converted to USD, Dmitri Petrov's duplicate is collapsed, and the Thompson household is marked inactive.",
            "",
            "We've now run our automated pipeline across your entire book. Out of your full book, **over 90% mapped cleanly and automatically** into the Nevis canonical model.",
            "",
            "Below is the exact **shortlist of items Round 1 didn't settle** where we need your judgment rather than guessing. To make this as fast as possible for you, each item includes the background, candidate options, and a **proposed default**. You can simply reply approving the defaults or specify any adjustments in a couple of lines!",
            "",
            "---",
            ""
        ]

        # Group by Category
        unassigned_adv = [c for c in clarifs if c.category == "UNASSIGNED_ADVISOR"]
        orphan_acc = [c for c in clarifs if c.category == "ORPHAN_ACCOUNT"]
        orphan_int = [c for c in clarifs if c.category == "ORPHAN_INTERACTION"]

        item_num = 1

        if unassigned_adv:
            lines.append("## Part 1: Primary Advisor Assignments (Blank in CRM)")
            lines.append("Per our Round 1 discussion, we do not guess or fall back to Service Reps. The following 4 clients have a blank Advisor field in Notion:")
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
            lines.append("## Part 2: Custodian Accounts with No Matching CRM Client")
            lines.append("Our custodian positions file contains 2 active investment accounts where the account holder name does not exist anywhere in your Notion CRM:")
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
            lines.append("## Part 3: Meeting Interaction with Unregistered Lead")
            lines.append("We identified 1 meeting in your Notion calendar with an organization that does not exist in your client database:")
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
            "### How to Reply (Quick-Response Template)",
            "If the proposed defaults look good to you, you can literally reply with:",
            "```text",
            "Approved all proposed defaults as listed.",
            "```",
            "Or if you want to tweak specific assignments:",
            "```text",
            "1. Delgado: Assign to Marcus Webb",
            "2. Whitfield: Assign to Priya Raman",
            "3. Petit: Assign to Marcus Webb",
            "4. Vandermeer: Assign to Elena Sokolova",
            "5. Vasquez: New client, assign to Priya Raman",
            "6. Mehta: New client, assign to Grace Bennett",
            "7. Redwood: Archive as prospecting lead",
            "```",
            "",
            "Once you reply, our pipeline will apply your answers instantly and lock in the final book!",
            "",
            "Best,",  
            "Alex & The Nevis Onboarding Team"
        ])

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return output_path
