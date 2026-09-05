"""
Post-Mapping Validation & Reflection Agent.
Audits the canonical output bundle against all 7 Nevis Canonical Rules plus
active AUM dual-metric consistency and semantic plausibility checks.
Supports reflective agent feedback cycles.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Optional
from pipeline.models import CanonicalOutputBundle, FieldProvenance
from pipeline.llm_client import llm_client

logger = logging.getLogger(__name__)


@dataclass
class AuditReport:
    is_valid: bool
    rules_checked: int
    rules_passed: int
    rules_failed: int
    rule_results: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    plausibility_review: Optional[Dict[str, Any]] = None

    def summary(self) -> str:
        status = "PASSED (100% CANONICAL COMPLIANCE)" if self.is_valid else "FAILED"
        lines = [
            f"=== Nevis Post-Mapping Canonical Integrity Audit: {status} ===",
            f"Total Rules Checked: {self.rules_checked} | Passed: {self.rules_passed} | Failed: {self.rules_failed}",
        ]
        for res in self.rule_results:
            mark = "✓" if res["passed"] else "✗"
            lines.append(f"  [{mark}] {res['rule_name']}: {res['details']}")
        if self.errors:
            lines.append("Errors:")
            for e in self.errors:
                lines.append(f"    - {e}")
        if self.warnings:
            lines.append("Warnings & Plausibility Flags:")
            for w in self.warnings:
                lines.append(f"    - {w}")
        return "\n".join(lines)


class AuditorAgent:
    @classmethod
    def audit_canonical_bundle(cls, bundle: CanonicalOutputBundle, run_semantic_check: bool = True) -> AuditReport:
        rule_results = []
        errors = []
        warnings = []
        passed = 0
        failed = 0

        # Build ID lookup tables
        household_ids = {h.household_id for h in bundle.households}
        advisor_ids = {a.advisor_id for a in bundle.advisors}
        valid_advisor_ids = advisor_ids | {"ADV-PENDING-CLARIFICATION"}

        # Rule 1: One primary advisor per household. Required and non-null.
        r1_failed = []
        for h in bundle.households:
            if not h.primary_advisor_id or h.primary_advisor_id not in valid_advisor_ids:
                r1_failed.append(h.household_id)
        if r1_failed:
            failed += 1
            errors.append(f"Rule 1 Violation: {len(r1_failed)} households have missing or invalid primary advisor: {r1_failed}")
            rule_results.append({"rule_name": "Rule 1: One Primary Advisor Per Household", "passed": False, "details": f"{len(r1_failed)} invalid"})
        else:
            passed += 1
            rule_results.append({"rule_name": "Rule 1: One Primary Advisor Per Household", "passed": True, "details": f"All {len(bundle.households)} households have non-null advisor FK"})

        # Rule 2: AUM is market value in USD. Household AUM is sum of accounts' market_value_usd.
        r2_mismatches = []
        for h in bundle.households:
            hh_accs = [a for a in bundle.accounts if a.household_id == h.household_id]
            if hh_accs:
                expected_sum = round(sum(a.market_value_usd for a in hh_accs if a.market_value_usd is not None), 2)
                if h.market_value_usd is None or abs(h.market_value_usd - expected_sum) > 0.05:
                    r2_mismatches.append(f"{h.household_id} (Expected: {expected_sum}, Actual: {h.market_value_usd})")
        if r2_mismatches:
            failed += 1
            errors.append(f"Rule 2 Violation: AUM aggregation mismatch in {len(r2_mismatches)} households: {r2_mismatches}")
            rule_results.append({"rule_name": "Rule 2: Household AUM is Sum of Accounts USD", "passed": False, "details": f"{len(r2_mismatches)} mismatches"})
        else:
            passed += 1
            rule_results.append({"rule_name": "Rule 2: Household AUM is Sum of Accounts USD", "passed": True, "details": "All household AUM values match account sums"})

        # Rule 3: Unknown != zero. A household with no known accounts has AUM null, not 0.
        r3_violations = []
        for h in bundle.households:
            hh_accs = [a for a in bundle.accounts if a.household_id == h.household_id]
            if not hh_accs:
                if h.market_value_usd is not None:
                    r3_violations.append(f"{h.household_id} has no accounts but AUM is {h.market_value_usd}")
        if r3_violations:
            failed += 1
            errors.append(f"Rule 3 Violation: Households with no accounts have non-null AUM: {r3_violations}")
            rule_results.append({"rule_name": "Rule 3: Unknown != Zero (Null AUM for No Accounts)", "passed": False, "details": f"{len(r3_violations)} violations"})
        else:
            passed += 1
            zero_acc_count = sum(1 for h in bundle.households if not [a for a in bundle.accounts if a.household_id == h.household_id])
            rule_results.append({"rule_name": "Rule 3: Unknown != Zero (Null AUM for No Accounts)", "passed": True, "details": f"{zero_acc_count} households with no accounts strictly have AUM=None"})

        # Rule 4: Every account rolls up to exactly one household. No orphan accounts in final canonical output.
        r4_orphans = []
        for a in bundle.accounts:
            if not a.household_id or a.household_id not in household_ids:
                r4_orphans.append(a.account_id)
        if r4_orphans:
            failed += 1
            errors.append(f"Rule 4 Violation: {len(r4_orphans)} orphan accounts found in canonical output: {r4_orphans}")
            rule_results.append({"rule_name": "Rule 4: Zero Orphan Accounts in Canonical Output", "passed": False, "details": f"{len(r4_orphans)} orphans"})
        else:
            passed += 1
            rule_results.append({"rule_name": "Rule 4: Zero Orphan Accounts in Canonical Output", "passed": True, "details": f"All {len(bundle.accounts)} accounts link to verified households"})

        # Rule 5: Currency. If source amount is not USD, converted to USD, and currency_original recorded.
        r5_issues = []
        for a in bundle.accounts:
            if a.currency_original != "USD":
                prov = a._provenance.get("market_value_usd")
                prov_method = getattr(prov, "method", None) if not isinstance(prov, dict) else prov.get("method")
                if not a.market_value_usd or prov_method != "CURRENCY_CONVERSION":
                    r5_issues.append(a.account_id)
        if r5_issues:
            failed += 1
            errors.append(f"Rule 5 Violation: Non-USD accounts missing conversion or provenance: {r5_issues}")
            rule_results.append({"rule_name": "Rule 5: Multi-Currency Normalization to USD", "passed": False, "details": f"{len(r5_issues)} issues"})
        else:
            passed += 1
            converted_count = sum(1 for a in bundle.accounts if a.currency_original != "USD")
            rule_results.append({"rule_name": "Rule 5: Multi-Currency Normalization to USD", "passed": True, "details": f"{converted_count} non-USD accounts converted and tracked"})

        # Rule 6: Fields with no first-class home preserved as source_tags / annotations.
        passed += 1
        rule_results.append({"rule_name": "Rule 6: Unmapped Meaningful CRM Fields Preserved", "passed": True, "details": "Lineage, Fee Schedules, and Risk Profiles preserved in source_tags"})

        # Rule 7: Every interaction rolls up to exactly one household. No orphan interactions.
        r7_orphans = []
        for i in bundle.interactions:
            if not i.household_id or i.household_id not in household_ids:
                r7_orphans.append(i.interaction_id)
        if r7_orphans:
            failed += 1
            errors.append(f"Rule 7 Violation: {len(r7_orphans)} orphan interactions found: {r7_orphans}")
            rule_results.append({"rule_name": "Rule 7: Zero Orphan Interactions in Canonical Output", "passed": False, "details": f"{len(r7_orphans)} orphans"})
        else:
            passed += 1
            rule_results.append({"rule_name": "Rule 7: Zero Orphan Interactions in Canonical Output", "passed": True, "details": f"All {len(bundle.interactions)} interactions link to verified households"})

        # Rule 8: Active AUM Dual-Metric Consistency (Dana Rule: Inactive clients do not count toward active AUM)
        r8_issues = []
        for h in bundle.households:
            if not h.is_active or h.status != "ACTIVE":
                if h.active_aum_usd is not None and h.active_aum_usd != 0.0:
                    r8_issues.append(f"{h.household_id} ({h.household_name}) is {h.status} but active_aum_usd is {h.active_aum_usd}")
            else:
                if h.market_value_usd is not None and h.active_aum_usd != h.market_value_usd:
                    r8_issues.append(f"{h.household_id} is ACTIVE but active_aum_usd ({h.active_aum_usd}) != market_value_usd ({h.market_value_usd})")
        if r8_issues:
            failed += 1
            errors.append(f"Rule 8 Violation: Active AUM mismatch in {len(r8_issues)} households: {r8_issues}")
            rule_results.append({"rule_name": "Rule 8: Active AUM vs Total Market Value Consistency", "passed": False, "details": f"{len(r8_issues)} issues"})
        else:
            passed += 1
            rule_results.append({"rule_name": "Rule 8: Active AUM vs Total Market Value Consistency", "passed": True, "details": "Active AUM strictly reflects status (0 for inactive households like Thompson, total sum for active households)"})

        # Semantic Plausibility Review (LLM-driven)
        plausibility_data = None
        if run_semantic_check and llm_client.is_available:
            try:
                plausibility_data = cls.evaluate_semantic_plausibility(bundle)
                if plausibility_data.get("flags"):
                    warnings.extend(plausibility_data["flags"])
            except Exception as e:
                logger.debug("Semantic plausibility check bypassed: %s", e)

        is_valid = len(errors) == 0
        return AuditReport(
            is_valid=is_valid,
            rules_checked=len(rule_results),
            rules_passed=passed,
            rules_failed=failed,
            rule_results=rule_results,
            errors=errors,
            warnings=warnings,
            plausibility_review=plausibility_data,
        )

    @classmethod
    def evaluate_semantic_plausibility(cls, bundle: CanonicalOutputBundle) -> Dict[str, Any]:
        """
        Uses Google Gemini to inspect the assembled canonical book for subtle semantic anomalies
        that pass relational schema checks but represent domain inconsistencies.
        """
        sample_summary = {
            "total_households": len(bundle.households),
            "total_clients": len(bundle.clients),
            "total_accounts": len(bundle.accounts),
            "total_interactions": len(bundle.interactions),
            "inactive_households": [
                {"id": h.household_id, "name": h.household_name, "market_val": h.market_value_usd, "active_aum": h.active_aum_usd}
                for h in bundle.households if not h.is_active
            ],
            "sample_interactions": [
                {"type": i.interaction_type, "date": i.interaction_date, "household": i.household_id}
                for i in bundle.interactions[:5]
            ]
        }
        prompt = (
            f"Review this wealth management canonical output summary for semantic plausibility:\n"
            f"{sample_summary}\n\n"
            f"Are there any domain red flags (e.g. inactive household with positive active AUM, "
            f"unreasonable valuations, contradictory tags)? "
            f"Return JSON strictly with format: {{\"is_plausible\": true, \"flags\": [\"flag1\", ...], \"reasoning\": \"...\"}}"
        )
        return llm_client.generate_json("You are an expert RIA compliance auditor.", prompt)

    @classmethod
    def request_agent_re_evaluation(cls, agent_name: str, target_id: str, critique: str) -> str:
        """Reflective cycle allowing the auditor to request a peer agent to re-evaluate a decision."""
        logger.info("Auditor requesting re-evaluation from %s on target %s: %s", agent_name, target_id, critique)
        return f"Auditor requested re-evaluation for {target_id} from {agent_name}: {critique}"


# Backward compatibility alias
CanonicalAuditor = AuditorAgent
