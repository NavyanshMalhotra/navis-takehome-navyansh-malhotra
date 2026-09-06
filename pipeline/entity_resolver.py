"""
Entity Resolver & Disambiguation Agent.
Resolves custodian account holding entities (Trusts, LLCs, Joint co-holders,
inverted names, and diminutives) to canonical Households and Clients.
Combines deterministic onomastic heuristics with Google GenAI agentic reasoning.
"""

import re
import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple, Set

from google.adk.agents import BaseAgent
from config import config
from pipeline.llm_client import llm_client
from pipeline.telemetry import telemetry

logger = logging.getLogger(__name__)

STANDARD_DIMINUTIVES: Dict[str, Set[str]] = {
    "bill": {"william", "billy"},
    "will": {"william", "willie"},
    "bob": {"robert", "bobby", "rob"},
    "rob": {"robert"},
    "jim": {"james", "jimmy"},
    "dick": {"richard", "rick"},
    "rich": {"richard"},
    "dan": {"daniel", "danny"},
    "mike": {"michael"},
    "tom": {"thomas", "tommy"},
    "tony": {"anthony"},
    "chris": {"christopher", "christian"},
    "dave": {"david"},
    "ed": {"edward", "edwin", "edgar"},
    "ted": {"edward", "theodore"},
    "alex": {"alexander", "alexandra"},
    "pat": {"patrick", "patricia"},
    "sam": {"samuel", "samantha"},
    "steve": {"stephen", "steven"},
    "liz": {"elizabeth", "beth"},
    "kate": {"katherine", "catherine"},
    "peg": {"margaret", "peggy"},
    "jack": {"john"},
    "hank": {"henry"},
    "chuck": {"charles"},
}


@dataclass
class EntityResolutionResult:
    account_number: str
    raw_holder: str
    matched_household_id: Optional[str]
    matched_client_id: Optional[str]
    resolved_account_type: str
    confidence: float
    resolution_method: str
    reasoning: str
    is_orphan: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_number": self.account_number,
            "raw_holder": self.raw_holder,
            "matched_household_id": self.matched_household_id,
            "matched_client_id": self.matched_client_id,
            "resolved_account_type": self.resolved_account_type,
            "confidence": self.confidence,
            "resolution_method": self.resolution_method,
            "reasoning": self.reasoning,
            "is_orphan": self.is_orphan,
        }


class EntityResolverAgent(BaseAgent):
    """Google ADK agent for legal entity disambiguation and onomastic resolution."""

    name: str = "EntityResolverAgent"
    description: str = "Disambiguates legal entities, trusts, joint accounts, and personal aliases."

    def __init__(self, **data):
        super().__init__(**data)
        prompt_path = config.prompts_dir / "entity_resolution.txt"
        system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""
        object.__setattr__(self, "system_prompt", system_prompt)
        object.__setattr__(self, "_alias_cache", {})

    def normalize_name(self, name: str) -> str:
        if not name:
            return ""
        return " ".join(name.strip().split())

    def parse_inverted_name(self, name: str) -> Tuple[str, str]:
        if "," in name:
            parts = [p.strip() for p in name.split(",", 1)]
            if len(parts) == 2:
                return parts[1], parts[0]
        parts = name.split()
        if len(parts) >= 2:
            return parts[0], parts[-1]
        elif len(parts) == 1:
            return parts[0], ""
        return "", ""

    def extract_trust_grantor(self, text: str) -> Optional[str]:
        pattern = re.compile(
            r"^(.*?)\s+(?:revocable\s+trust|irrevocable\s+trust|living\s+trust|family\s+trust|revocable|trust)$",
            re.IGNORECASE
        )
        match = pattern.match(text.strip())
        if match:
            grantor = match.group(1).strip()
            if grantor.lower().startswith("the "):
                grantor = grantor[4:].strip()
            return grantor
        return None

    def extract_joint_holders(self, text: str) -> List[str]:
        joint_pattern = re.compile(r"^(.*?)\s+(?:&|and)\s+(.*?)(?:\s+(?:jtwros|joint|wros))?$", re.IGNORECASE)
        match = joint_pattern.match(text.strip())
        if match:
            person_a = match.group(1).strip()
            person_b = match.group(2).strip()
            tokens_b = person_b.split()
            if len(tokens_b) >= 2 and len(person_a.split()) == 1:
                surname = tokens_b[-1]
                person_a_full = f"{person_a} {surname}"
                return [person_a_full, person_b]
            return [person_a, person_b]
        return []

    def is_diminutive_or_alias(self, candidate_first: str, target_first: str) -> bool:
        c = candidate_first.lower().strip()
        t = target_first.lower().strip()
        if not c or not t:
            return False
        if c == t:
            return True

        cache_key = f"{c}:{t}"
        if cache_key in self._alias_cache:
            return self._alias_cache[cache_key]

        # 1. Deterministic standard diminutives lookup
        if (c in STANDARD_DIMINUTIVES and t in STANDARD_DIMINUTIVES[c]) or (
            t in STANDARD_DIMINUTIVES and c in STANDARD_DIMINUTIVES[t]
        ):
            self._alias_cache[cache_key] = True
            return True

        # 2. LLM reasoning for non-standard variants
        if not llm_client.is_available:
            self._alias_cache[cache_key] = False
            return False

        prompt = (
            f"In wealth management entity resolution, is '{c.title()}' a standard "
            f"or recognizable diminutive, nickname, or given name variation of '{t.title()}'?\n"
            f"Respond with JSON strictly matching: {{\"is_match\": true, \"confidence\": 0.95, \"reasoning\": \"...\"}}"
        )
        try:
            with telemetry.trace_tool("llm_onomastic_reasoning", candidate=c, target=t):
                res = llm_client.generate_json("You are an expert onomastics and entity disambiguation specialist.", prompt)
            is_match = bool(res.get("is_match", False))
            self._alias_cache[cache_key] = is_match
            return is_match
        except Exception as exc:
            logger.debug("LLM alias resolution failed for %s vs %s: %s", c, t, exc)
            self._alias_cache[cache_key] = False
            return False

    def resolve_account_holder(
        self,
        account: Dict[str, Any],
        clients: List[Dict[str, Any]],
        households: List[Dict[str, Any]],
        doc_miner_insights: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> EntityResolutionResult:
        """Resolves custodian account holder to canonical Household and Client."""
        acc_num = str(account.get("Account_Number", "")).strip()
        holder = self.normalize_name(str(account.get("Account_Holder", "")))
        source_acc_type = str(account.get("Account_Type", "")).strip()
        doc_miner_insights = doc_miner_insights or {}

        client_by_name = {self.normalize_name(c.get("Name", "")).lower(): c for c in clients}

        # 1. Exact Name Match
        holder_lower = holder.lower()
        if holder_lower in client_by_name:
            matched_client = client_by_name[holder_lower]
            return EntityResolutionResult(
                account_number=acc_num,
                raw_holder=holder,
                matched_household_id=matched_client.get("household_id"),
                matched_client_id=matched_client.get("client_id"),
                resolved_account_type=self._normalize_account_type(source_acc_type),
                confidence=0.98,
                resolution_method="EXACT_NAME_MATCH",
                reasoning=f"Exact match on client name '{holder}' across custodian and CRM systems."
            )

        # 2. Inverted Name Normalization ('Last, First' -> 'First Last')
        first, last = self.parse_inverted_name(holder)
        if first and last:
            inverted = f"{first} {last}".lower()
            if inverted in client_by_name:
                matched_client = client_by_name[inverted]
                return EntityResolutionResult(
                    account_number=acc_num,
                    raw_holder=holder,
                    matched_household_id=matched_client.get("household_id"),
                    matched_client_id=matched_client.get("client_id"),
                    resolved_account_type=self._normalize_account_type(source_acc_type),
                    confidence=0.96,
                    resolution_method="INVERTED_NAME_NORMALIZATION",
                    reasoning=f"Inverted name '{holder}' normalized to '{first} {last}'."
                )

        # 3. Trust Grantor Resolution
        trust_grantor = self.extract_trust_grantor(holder)
        if trust_grantor:
            grantor_norm = self.normalize_name(trust_grantor).lower()
            if grantor_norm in client_by_name:
                matched_client = client_by_name[grantor_norm]
                return EntityResolutionResult(
                    account_number=acc_num,
                    raw_holder=holder,
                    matched_household_id=matched_client.get("household_id"),
                    matched_client_id=matched_client.get("client_id"),
                    resolved_account_type="TRUST",
                    confidence=0.97,
                    resolution_method="TRUST_GRANTOR_DISAMBIGUATION",
                    reasoning=f"Trust entity '{holder}' resolved to grantor '{trust_grantor}'."
                )

        # 4. Dossier Notes Affiliations
        for c_name, insights in doc_miner_insights.items():
            affiliated = [e.lower() for e in insights.get("affiliated_entities", [])]
            raw_snippets = insights.get("raw_snippets", [])
            if holder_lower in affiliated or any(holder_lower in snip.lower() for snip in raw_snippets):
                cand_client = client_by_name.get(c_name.lower())
                if cand_client:
                    return EntityResolutionResult(
                        account_number=acc_num,
                        raw_holder=holder,
                        matched_household_id=cand_client.get("household_id"),
                        matched_client_id=cand_client.get("client_id"),
                        resolved_account_type="CORPORATE" if "llc" in holder_lower or "holdings" in holder_lower else "OTHER",
                        confidence=0.93,
                        resolution_method="DOC_MINER_AFFILIATION_MATCH",
                        reasoning=f"Entity '{holder}' matched to client '{c_name}' via CRM dossier notes."
                    )

        # 5. Joint Account Co-Holders
        joint_holders = self.extract_joint_holders(holder)
        if joint_holders:
            for jh in joint_holders:
                jh_norm = self.normalize_name(jh).lower()
                jh_tokens = jh_norm.split()
                target_client = client_by_name.get(jh_norm)
                if not target_client and jh_tokens:
                    first_tok = jh_tokens[0]
                    last_tok = jh_tokens[-1] if len(jh_tokens) > 1 else ""
                    for c_name_clean, c_record in client_by_name.items():
                        c_tokens = c_name_clean.split()
                        if len(c_tokens) >= 2:
                            c_first, c_last = c_tokens[0], c_tokens[-1]
                            if (not last_tok or last_tok == c_last) and self.is_diminutive_or_alias(first_tok, c_first):
                                target_client = c_record
                                break

                if target_client:
                    return EntityResolutionResult(
                        account_number=acc_num,
                        raw_holder=holder,
                        matched_household_id=target_client.get("household_id"),
                        matched_client_id=target_client.get("client_id"),
                        resolved_account_type="JOINT",
                        confidence=0.96,
                        resolution_method="JOINT_ACCOUNT_SPOUSAL_RESOLUTION",
                        reasoning=f"Joint account holder '{holder}' matched to client '{target_client.get('Name')}'."
                    )

        # 6. Surname Joint / Family Account
        surname_match = re.match(r"^(.*?)\s+(?:joint\s+wros|jtwros|joint|family)$", holder, re.IGNORECASE)
        if surname_match:
            stem = surname_match.group(1).strip().lower()
            for hh_obj in households:
                hh_clean = hh_obj.get("household_name", "").lower()
                hh_id_val = hh_obj.get("household_id", "")
                if stem in hh_clean or stem in hh_id_val.lower():
                    cand_client = next((c for c in clients if c.get("household_id") == hh_id_val), None)
                    return EntityResolutionResult(
                        account_number=acc_num,
                        raw_holder=holder,
                        matched_household_id=hh_id_val,
                        matched_client_id=cand_client.get("client_id") if cand_client else None,
                        resolved_account_type="JOINT",
                        confidence=0.95,
                        resolution_method="SURNAME_JOINT_HOUSEHOLD_RESOLUTION",
                        reasoning=f"Surname joint holder '{holder}' matched to household '{hh_obj.get('household_name')}'."
                    )

        # 7. Single-Holder Nickname Resolution
        holder_tokens = holder_lower.split()
        if len(holder_tokens) >= 2:
            cand_first = holder_tokens[0]
            cand_last = holder_tokens[-1]
            for c_name_clean, c_record in client_by_name.items():
                c_tokens = c_name_clean.split()
                if len(c_tokens) >= 2:
                    c_first, c_last = c_tokens[0], c_tokens[-1]
                    if c_last == cand_last and c_first != cand_first and self.is_diminutive_or_alias(cand_first, c_first):
                        return EntityResolutionResult(
                            account_number=acc_num,
                            raw_holder=holder,
                            matched_household_id=c_record.get("household_id"),
                            matched_client_id=c_record.get("client_id"),
                            resolved_account_type=self._normalize_account_type(source_acc_type),
                            confidence=0.95,
                            resolution_method="ONOMASTIC_ALIAS_RESOLUTION",
                            reasoning=f"'{holder}' matched to '{c_record.get('Name')}' via nickname resolution ('{cand_first}' -> '{c_first}')."
                        )

        # 8. LLM Disambiguation for Complex Holdings
        holder_tokens = set(holder_lower.split())
        has_token_overlap = any(bool(holder_tokens.intersection(set(c_name.split()))) for c_name in client_by_name)
        is_entity_type = any(kw in holder_lower for kw in ("llc", "trust", "corp", "inc", "holdings", "ltd", "lp", "fund", "family"))

        if llm_client.is_available and (has_token_overlap or is_entity_type):
            try:
                candidates = [
                    {"name": c.get("Name"), "household": c.get("household_id"), "segment": c.get("Segment")}
                    for c in clients
                ]
                llm_prompt = (
                    f"Custodian Account Holder: '{holder}'\n"
                    f"Source Account Type: '{source_acc_type}'\n"
                    f"Known Clients & Households: {json.dumps(candidates)}\n\n"
                    f"Determine which client and household this account belongs to. "
                    f"If there is a clear match, return client name and confidence >= 0.80. "
                    f"If not matched, set is_orphan=true and confidence < 0.50.\n"
                    f"Return JSON strictly matching: {{\"matched_name\": \"...\", \"account_type\": \"...\", \"confidence\": 0.90, \"reasoning\": \"...\", \"is_orphan\": false}}"
                )
                with telemetry.trace_tool("llm_entity_disambiguation", holder=holder):
                    llm_resp = llm_client.generate_json(self.system_prompt, llm_prompt)
                matched_name = llm_resp.get("matched_name")
                matched_client = client_by_name.get(matched_name.lower()) if matched_name else None

                if matched_client and not llm_resp.get("is_orphan"):
                    confidence_val = float(llm_resp.get("confidence", 0.0))
                    if confidence_val >= config.confidence_high_threshold:
                        return EntityResolutionResult(
                            account_number=acc_num,
                            raw_holder=holder,
                            matched_household_id=matched_client.get("household_id"),
                            matched_client_id=matched_client.get("client_id"),
                            resolved_account_type=self._normalize_account_type(llm_resp.get("account_type", source_acc_type)),
                            confidence=confidence_val,
                            resolution_method="LLM_AGENT_DISAMBIGUATION",
                            reasoning=llm_resp.get("reasoning", f"LLM resolved '{holder}' to '{matched_name}'.")
                        )
            except Exception as exc:
                logger.debug("LLM entity disambiguation skipped for %s: %s", holder, exc)

        # 9. Unmatched Orphan Account
        return EntityResolutionResult(
            account_number=acc_num,
            raw_holder=holder,
            matched_household_id=None,
            matched_client_id=None,
            resolved_account_type=self._normalize_account_type(source_acc_type),
            confidence=0.20,
            resolution_method="UNMAPPED_ORPHAN_ACCOUNT",
            reasoning=f"Account holder '{holder}' could not be matched with high confidence to any client in CRM.",
            is_orphan=True,
        )

    def resolve_account_to_household(
        self,
        account: Dict[str, Any],
        households: List[Dict[str, Any]],
        clients: List[Dict[str, Any]],
        doc_miner_insights: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> EntityResolutionResult:
        return self.resolve_account_holder(account, clients, households, doc_miner_insights)

    def _normalize_account_type(self, raw_type: str) -> str:
        t = raw_type.upper().strip() if raw_type else "INDIVIDUAL"
        if "ROTH" in t:
            return "ROTH_IRA"
        elif "IRA" in t or "ROLLOVER" in t or "SEP" in t:
            return "IRA"
        elif "TRUST" in t:
            return "TRUST"
        elif "JOINT" in t or "WROS" in t:
            return "JOINT"
        elif "CORP" in t or "LLC" in t:
            return "CORPORATE"
        elif "INDIVIDUAL" in t:
            return "INDIVIDUAL"
        return "OTHER"
