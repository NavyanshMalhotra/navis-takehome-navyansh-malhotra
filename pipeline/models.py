"""
Nevis Canonical Data Model and Provenance Lineage Schemas.
Implements the 5 canonical entities with field-level audit trails.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

@dataclass
class FieldProvenance:
    source_file: str
    source_location: str  # e.g., "Row 2", "Lines 14-24", "Header"
    source_raw_value: Any
    method: str  # DETERMINISTIC_DIRECT, RULE_ENGINE, LLM_AGENT_REASONING, HUMAN_SLACK_INPUT
    confidence: float
    rule_or_agent: str
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Household:
    household_id: str
    household_name: str
    primary_advisor_id: str
    status: str  # ACTIVE | INACTIVE | PROSPECT
    as_of_date: str
    source_tags: List[str] = field(default_factory=list)
    market_value_usd: Optional[float] = None  # Aggregated household AUM
    _provenance: Dict[str, FieldProvenance] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["_provenance"] = {k: v.to_dict() if isinstance(v, FieldProvenance) else v for k, v in self._provenance.items()}
        return res

@dataclass
class Client:
    client_id: str
    household_id: str
    first_name: str
    last_name: str
    role: str  # PRIMARY | SPOUSE | DEPENDENT | SIGNER | OTHER
    source_tags: List[str] = field(default_factory=list)
    _provenance: Dict[str, FieldProvenance] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["_provenance"] = {k: v.to_dict() if isinstance(v, FieldProvenance) else v for k, v in self._provenance.items()}
        return res

@dataclass
class Account:
    account_id: str
    household_id: str
    account_type: str  # INDIVIDUAL | JOINT | TRUST | IRA | ROTH_IRA | CORPORATE | OTHER
    market_value_usd: Optional[float]
    currency_original: str
    as_of_date: str
    custodian: str
    account_holder_raw: str = ""
    _provenance: Dict[str, FieldProvenance] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["_provenance"] = {k: v.to_dict() if isinstance(v, FieldProvenance) else v for k, v in self._provenance.items()}
        return res

@dataclass
class Advisor:
    advisor_id: str
    full_name: str
    role: str
    office: str = ""
    _provenance: Dict[str, FieldProvenance] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["_provenance"] = {k: v.to_dict() if isinstance(v, FieldProvenance) else v for k, v in self._provenance.items()}
        return res

@dataclass
class Interaction:
    interaction_id: str
    household_id: str
    interaction_type: str  # REVIEW | PROSPECTING | ONBOARDING | OTHER
    interaction_date: str
    advisor_id: Optional[str]
    summary: Optional[str]
    attendee_raw: str = ""
    _provenance: Dict[str, FieldProvenance] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["_provenance"] = {k: v.to_dict() if isinstance(v, FieldProvenance) else v for k, v in self._provenance.items()}
        return res

@dataclass
class ClarificationItem:
    id: str
    category: str  # UNASSIGNED_ADVISOR | ORPHAN_ACCOUNT | ORPHAN_INTERACTION | AMBIGUOUS_MATCH
    title: str
    trigger: str
    evidence: str
    candidate_options: List[str]
    proposed_default: str
    confidence: float
    status: str = "PENDING_REVIEW"  # PENDING_REVIEW | RESOLVED
    entity_ref: str = ""  # ID or reference of item
    resolved_value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class CanonicalOutputBundle:
    households: List[Household] = field(default_factory=list)
    clients: List[Client] = field(default_factory=list)
    accounts: List[Account] = field(default_factory=list)
    advisors: List[Advisor] = field(default_factory=list)
    interactions: List[Interaction] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata,
            "households": [h.to_dict() for h in self.households],
            "clients": [c.to_dict() for c in self.clients],
            "accounts": [a.to_dict() for a in self.accounts],
            "advisors": [adv.to_dict() for adv in self.advisors],
            "interactions": [i.to_dict() for i in self.interactions],
        }
