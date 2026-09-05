"""
Pre-Flight Source Validation Suite.
Audits incoming source files against expected schemas and invariants before mapping begins.
Catches data corruption, missing columns, unexpected currencies, or missing notes early.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Set
from pathlib import Path

@dataclass
class SourceValidationReport:
    is_valid: bool
    checks_passed: int
    checks_failed: int
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        status = "PASSED" if self.is_valid else "FAILED"
        lines = [
            f"=== Source Data Pre-Flight Validation: {status} ===",
            f"Checks Passed: {self.checks_passed} | Checks Failed: {self.checks_failed}",
            f"Total Advisors: {self.stats.get('advisor_count', 0)}",
            f"Total CRM Clients: {self.stats.get('client_count', 0)} (Markdown Pages Linked: {self.stats.get('client_pages_linked', 0)})",
            f"Total Meetings: {self.stats.get('meeting_count', 0)} (Markdown Pages Linked: {self.stats.get('meeting_pages_linked', 0)})",
            f"Total Custodian Accounts: {self.stats.get('custodian_account_count', 0)}",
            f"Currencies Detected: {', '.join(self.stats.get('currencies_detected', []))}",
        ]
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  [WARN] {w}")
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  [ERROR] {e}")
        return "\n".join(lines)


class SourceValidationSuite:
    REQUIRED_ADVISOR_COLS = {"advisor_id", "full_name", "role"}
    REQUIRED_CUSTODIAN_COLS = {"Account_Number", "Account_Holder", "Account_Type", "Market_Value", "Currency", "As_Of_Date", "Custodian"}
    REQUIRED_CLIENT_COLS = {"Name", "Status", "Advisor", "Service Rep", "Household"}
    REQUIRED_MEETING_COLS = {"Name", "Client", "Type", "Date"}

    @classmethod
    def audit_sources(
        cls,
        advisors: List[Dict[str, Any]],
        clients: List[Dict[str, Any]],
        meetings: List[Dict[str, Any]],
        custodian_accounts: List[Dict[str, Any]],
    ) -> SourceValidationReport:
        passed = 0
        failed = 0
        warnings = []
        errors = []
        stats: Dict[str, Any] = {}

        # 1. Advisor Roster Audit
        stats["advisor_count"] = len(advisors)
        if not advisors:
            errors.append("Advisor roster is empty.")
            failed += 1
        else:
            adv_keys = set(advisors[0].keys())
            missing_adv = cls.REQUIRED_ADVISOR_COLS - adv_keys
            if missing_adv:
                errors.append(f"Advisor roster missing required columns: {missing_adv}")
                failed += 1
            else:
                passed += 1

        # 2. Custodian Positions Audit
        stats["custodian_account_count"] = len(custodian_accounts)
        currencies: Set[str] = set()
        if not custodian_accounts:
            errors.append("Custodian positions file is empty.")
            failed += 1
        else:
            cust_keys = set(custodian_accounts[0].keys())
            missing_cust = cls.REQUIRED_CUSTODIAN_COLS - cust_keys
            if missing_cust:
                errors.append(f"Custodian positions missing required columns: {missing_cust}")
                failed += 1
            else:
                passed += 1

            for acc in custodian_accounts:
                curr = acc.get("Currency", "").strip()
                if curr:
                    currencies.add(curr)
                # Check market value is parseable number
                val_raw = acc.get("Market_Value", "")
                if val_raw:
                    try:
                        float(val_raw)
                    except ValueError:
                        warnings.append(f"Account {acc.get('Account_Number')} has non-numeric Market_Value: '{val_raw}'")

        stats["currencies_detected"] = sorted(list(currencies))
        non_usd = currencies - {"USD"}
        if non_usd:
            warnings.append(f"Non-USD currencies detected: {non_usd}. Currency conversion required (Canonical Rule 5).")

        # 3. Notion Clients Audit
        stats["client_count"] = len(clients)
        client_pages_count = sum(1 for c in clients if c.get("_page_body"))
        stats["client_pages_linked"] = client_pages_count
        if not clients:
            errors.append("Notion Clients dataset is empty.")
            failed += 1
        else:
            client_keys = set(clients[0].keys())
            missing_client = cls.REQUIRED_CLIENT_COLS - client_keys
            if missing_client:
                errors.append(f"Notion Clients CSV missing required columns: {missing_client}")
                failed += 1
            else:
                passed += 1

            blank_advisors = [c["Name"] for c in clients if not c.get("Advisor", "").strip()]
            if blank_advisors:
                warnings.append(f"{len(blank_advisors)} clients have blank Advisor field: {blank_advisors[:4]}...")

        # 4. Notion Meetings Audit
        stats["meeting_count"] = len(meetings)
        meeting_pages_count = sum(1 for m in meetings if m.get("_page_body"))
        stats["meeting_pages_linked"] = meeting_pages_count
        if not meetings:
            errors.append("Notion Meetings dataset is empty.")
            failed += 1
        else:
            meet_keys = set(meetings[0].keys())
            missing_meet = cls.REQUIRED_MEETING_COLS - meet_keys
            if missing_meet:
                errors.append(f"Notion Meetings CSV missing required columns: {missing_meet}")
                failed += 1
            else:
                passed += 1

        is_valid = len(errors) == 0
        return SourceValidationReport(
            is_valid=is_valid,
            checks_passed=passed,
            checks_failed=failed,
            warnings=warnings,
            errors=errors,
            stats=stats,
        )
