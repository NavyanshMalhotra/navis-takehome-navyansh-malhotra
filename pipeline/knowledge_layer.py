"""
Knowledge Layer & Declarative Business Rules Engine.
Encodes stakeholder operational knowledge (Dana Ruiz's Slack Round 1 answers)
and reusable RIA onboarding rules.
Supports dynamic rule injection when new clarification questions are resolved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Tuple, Callable
from config import config

@dataclass
class KnowledgeRule:
    rule_id: str
    category: str
    description: str
    stakeholder: str
    source_reference: str
    scope: str  # "CLIENT_SPECIFIC" | "CROSS_CLIENT_REUSABLE"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "description": self.description,
            "stakeholder": self.stakeholder,
            "source_reference": self.source_reference,
            "scope": self.scope,
            "metadata": self.metadata,
        }

class KnowledgeEngine:
    def __init__(self):
        self.rules: Dict[str, KnowledgeRule] = {}
        self._load_slack_round1_rules()

    def _load_slack_round1_rules(self):
        """Encodes the 7 critical operational rules answered by Dana Ruiz in Slack Round 1."""
        
        # Rule 1: Legacy Status -> Harborline Book
        self.register_rule(KnowledgeRule(
            rule_id="RULE_LEGACY_IS_HARBORLINE_ACTIVE",
            category="CLIENT_STATUS",
            description="Status 'Legacy' represents the book acquired from Harborline Advisors in 2019. Operationally active clients, but must preserve Harborline acquisition lineage.",
            stakeholder="Dana Ruiz (Head of Operations)",
            source_reference="sources/ops_slack_thread.md:Lines 14-24",
            scope="CLIENT_SPECIFIC",
            metadata={
                "input_status": "Legacy",
                "canonical_status": "ACTIVE",
                "add_source_tag": "acquired from Harborline"
            }
        ))

        # Rule 2: Real Advisor vs Service Rep
        self.register_rule(KnowledgeRule(
            rule_id="RULE_ADVISOR_VS_SERVICE_REP",
            category="ADVISOR_PRECEDENCE",
            description="Advisor field represents relationship owner. Service Rep is junior/ops paperwork handler. If Advisor is blank, NEVER fallback to Service Rep. Flag for human assignment.",
            stakeholder="Dana Ruiz (Head of Operations)",
            source_reference="sources/ops_slack_thread.md:Lines 31-42",
            scope="CROSS_CLIENT_REUSABLE",
            metadata={"allow_service_rep_fallback": False}
        ))

        # Rule 3: Departed Contractor A. Novak
        self.register_rule(KnowledgeRule(
            rule_id="RULE_DEPARTED_STAFF_NOVAK",
            category="DEPARTED_STAFF",
            description="Anna Novak (A. Novak) was a contractor who left in 2024. Any client records or meetings with her must be surfaced for reassignment.",
            stakeholder="Dana Ruiz (Head of Operations)",
            source_reference="sources/ops_slack_thread.md:Lines 42-46",
            scope="CLIENT_SPECIFIC",
            metadata={"departed_staff_names": ["A. Novak", "Anna Novak"]}
        ))

        # Rule 4: AUM Definition (Market Value over Cost Basis)
        self.register_rule(KnowledgeRule(
            rule_id="RULE_AUM_MARKET_VALUE_ONLY",
            category="AUM_CALCULATION",
            description="Firm AUM is strictly based on Market Value as of the most recent quarter-end. Ignore Cost Basis (tax-only).",
            stakeholder="Dana Ruiz (Head of Operations)",
            source_reference="sources/ops_slack_thread.md:Lines 51-54",
            scope="CROSS_CLIENT_REUSABLE",
            metadata={"value_column": "Market_Value", "ignore_column": "Cost_Basis"}
        ))

        # Rule 5: Foreign Currency Conversion
        self.register_rule(KnowledgeRule(
            rule_id="RULE_FOREIGN_CURRENCY_USD_REPORTING",
            category="CURRENCY_CONVERSION",
            description="Convert all non-USD balances to USD at quarter-end benchmark FX rate. Always record currency_original.",
            stakeholder="Dana Ruiz (Head of Operations)",
            source_reference="sources/ops_slack_thread.md:Lines 59-63",
            scope="CROSS_CLIENT_REUSABLE",
            metadata={"target_currency": "USD"}
        ))

        # Rule 6: Duplicate Client Consolidation (Petrov)
        self.register_rule(KnowledgeRule(
            rule_id="RULE_DEDUPLICATE_PETROV",
            category="ENTITY_DEDUPLICATION",
            description="Dmitri Petrov and 'Petrov, Dmitri' are known duplicates created during Notion import. Collapse into single client and single household.",
            stakeholder="Dana Ruiz (Head of Operations)",
            source_reference="sources/ops_slack_thread.md:Lines 68-70",
            scope="CLIENT_SPECIFIC",
            metadata={"primary_name": "Dmitri Petrov", "aliases": ["Petrov, Dmitri"]}
        ))

        # Rule 7: Churned Client Handling (Thompson)
        self.register_rule(KnowledgeRule(
            rule_id="RULE_CHURNED_CLIENT_THOMPSON",
            category="CHURNED_CLIENT",
            description="Thompson household left in 2023 and is winding down. Mark status as INACTIVE. Do not count toward active AUM.",
            stakeholder="Dana Ruiz (Head of Operations)",
            source_reference="sources/ops_slack_thread.md:Lines 70-73",
            scope="CLIENT_SPECIFIC",
            metadata={"household_name": "Thompson", "status": "INACTIVE"}
        ))

    def register_rule(self, rule: KnowledgeRule):
        self.rules[rule.rule_id] = rule

    def get_all_rules(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self.rules.values()]

    def map_client_status(self, raw_status: str) -> Tuple[str, List[str], Optional[KnowledgeRule]]:
        """
        Applies status normalization rules.
        e.g. 'Legacy' -> ('ACTIVE', ['acquired from Harborline'], rule)
             'Prospect' -> ('PROSPECT', [], None)
             'Active' -> ('ACTIVE', [], None)
        """
        clean = raw_status.strip().title() if raw_status else "ACTIVE"
        
        if clean.lower() == "legacy":
            rule = self.rules.get("RULE_LEGACY_IS_HARBORLINE_ACTIVE")
            return "ACTIVE", ["acquired from Harborline"], rule
        elif clean.lower() in ("prospect", "lead"):
            return "PROSPECT", [], None
        elif clean.lower() in ("former", "churned", "inactive"):
            return "INACTIVE", [], None
        elif clean.lower() in ("active", "client"):
            return "ACTIVE", [], None
        else:
            return "ACTIVE", [f"raw_status:{clean}"], None

    def is_departed_staff(self, name: str) -> bool:
        rule = self.rules.get("RULE_DEPARTED_STAFF_NOVAK")
        if not rule or not name:
            return False
        targets = [t.lower() for t in rule.metadata.get("departed_staff_names", [])]
        return any(t in name.lower() for t in targets)

    def is_known_duplicate_petrov(self, name: str) -> bool:
        rule = self.rules.get("RULE_DEDUPLICATE_PETROV")
        if not rule or not name:
            return False
        clean = name.lower().replace(",", " ").strip()
        return "petrov" in clean and "dmitri" in clean

    def convert_currency_to_usd(self, currency: str, amount: float) -> Tuple[float, float, str]:
        """
        Converts amount from source currency to USD using benchmark quarter-end FX rates.
        Returns: (usd_amount, fx_rate, reasoning)
        """
        curr = currency.upper().strip() if currency else "USD"
        rate = config.fx_rates_to_usd.get(curr, 1.0)
        usd_val = round(amount * rate, 2)
        reasoning = f"Converted {amount:,.2f} {curr} to USD @ {rate:.4f} (Q2 2025 benchmark rate)"
        return usd_val, rate, reasoning
