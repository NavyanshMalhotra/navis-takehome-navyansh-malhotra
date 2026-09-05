"""
Entity Resolver & Disambiguation Agent for Nevis Platform.
Disentangles legal entities (Trusts, LLCs), Joint account holders, inverted names,
initials, and nicknames to map custodian accounts to Households and Clients.
Combines deterministic normalization with Gemini-driven semantic reasoning.
"""

import re
import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Tuple
from config import config
from pipeline.llm_client import llm_client

logger = logging.getLogger(__name__)

# Standard Anglo Diminutive Map (generic; no overfitted client-specific names)
NICKNAME_MAP = {
    "bob": "robert",
    "bobby": "robert",
    "bill": "william",
    "billy": "william",
    "jim": "james",
    "jimmy": "james",
    "mike": "michael",
    "tom": "thomas",
    "tommy": "thomas",
    "liz": "elizabeth",
    "dan": "daniel",
    "danny": "daniel",
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


class EntityResolverAgent:
    def __init__(self):
        prompt_path = config.prompts_dir / "entity_resolution.txt"
        self.system_prompt = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    def normalize_name(self, name: str) -> str:
        """Normalizes spacing, punctuation, and casing."""
        if not name:
            return ""
        return " ".join(name.strip().split())

    def parse_inverted_name(self, name: str) -> Tuple[str, str]:
        """Detects 'Last, First' and returns ('First', 'Last')."""
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
        """
        Extracts natural person grantor from trust naming.
        e.g. 'Ada Okonkwo Revocable Trust' -> 'Ada Okonkwo'
        """
        trust_pattern = re.compile(
            r"^(.*?)\s+(?:revocable\s+trust|irrevocable\s+trust|living\s+trust|family\s+trust|revocable|trust)$",
            re.IGNORECASE
        )
        match = trust_pattern.match(text.strip())
        if match:
            grantor = match.group(1).strip()
            if grantor.lower().startswith("the "):
                grantor = grantor[4:].strip()
            return grantor
        return None

    def extract_joint_holders(self, text: str) -> List[str]:
        """
        Detects multiple natural persons in a joint holding.
        e.g. 'Bob & Linda Chen' -> ['Bob Chen', 'Linda Chen']
        """
        joint_pattern = re.compile(r"^(.*?)\s+(?:&|and)\s+(.*?)(?:\s+jtwros|\s+joint|\s+wros)?$", re.IGNORECASE)
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

    def extract_corporate_entity(self, text: str) -> Optional[str]:
        """Detects corporate or LLC holdings."""
        corp_pattern = re.compile(r"^(.*?)\s+(?:holdings\s+llc|llc|inc\.?|corp\.?|partners|ltd\.?)$", re.IGNORECASE)
        match = corp_pattern.match(text.strip())
        if match:
            return match.group(1).strip()
        return None

    def resolve_diminutive(self, first_name: str) -> str:
        """Looks up canonical Anglo given name from common nickname."""
        return NICKNAME_MAP.get(first_name.lower().strip(), first_name.lower().strip())

    def resolve_account_holder(
        self,
        account: Dict[str, Any],
        clients: List[Dict[str, Any]],
        households: List[Dict[str, Any]],
        doc_miner_insights: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> EntityResolutionResult:
        """
        Resolves a single custodian account holding string to a canonical Household and Client.
        Combines deterministic heuristics with LLM agentic disambiguation.
        """
        acc_num = str(account.get("Account_Number", "")).strip()
        holder = self.normalize_name(str(account.get("Account_Holder", "")))
        source_acc_type = str(account.get("Account_Type", "")).strip()
        doc_miner_insights = doc_miner_insights or {}

        client_by_name = {self.normalize_name(c.get("Name", "")).lower(): c for c in clients}

        # 1. Deterministic Exact Match
        holder_lower = holder.lower()
        if holder_lower in client_by_name:
            matched_client = client_by_name[holder_lower]
            norm_type = self._normalize_account_type(source_acc_type)
            return EntityResolutionResult(
                account_number=acc_num,
                raw_holder=holder,
                matched_household_id=matched_client.get("household_id"),
                matched_client_id=matched_client.get("client_id"),
                resolved_account_type=norm_type,
                confidence=1.00,
                resolution_method="EXACT_NAME_MATCH",
                reasoning=f"Exact match on client name '{holder}'."
            )

        # 2. Inverted Name Normalization ('Petrov, Dmitri' -> 'Dmitri Petrov')
        first, last = self.parse_inverted_name(holder)
        if first and last:
            inverted_reconstruct = f"{first} {last}".lower()
            if inverted_reconstruct in client_by_name:
                matched_client = client_by_name[inverted_reconstruct]
                norm_type = self._normalize_account_type(source_acc_type)
                return EntityResolutionResult(
                    account_number=acc_num,
                    raw_holder=holder,
                    matched_household_id=matched_client.get("household_id"),
                    matched_client_id=matched_client.get("client_id"),
                    resolved_account_type=norm_type,
                    confidence=0.98,
                    resolution_method="INVERTED_NAME_NORMALIZATION",
                    reasoning=f"Inverted name '{holder}' normalized to '{first} {last}'."
                )

        # 3. Trust Entity Resolution ('Ada Okonkwo Revocable Trust' -> 'Ada Okonkwo')
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

        # 4. Check DocMiner Insights for Entity Affiliations (e.g. Kenji Nakamura has 'Nakamura Holdings LLC')
        for c_name, insights in doc_miner_insights.items():
            affiliated = [e.lower() for e in insights.get("affiliated_entities", [])]
            raw_snippets = insights.get("raw_snippets", [])
            # Check if holder matches any affiliated entity
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

        # 5. Joint Account Resolution (e.g. 'Bob & Linda Chen')
        joint_holders = self.extract_joint_holders(holder)
        if joint_holders:
            for jh in joint_holders:
                jh_norm = self.normalize_name(jh).lower()
                jh_tokens = jh_norm.split()
                first_dim = self.resolve_diminutive(jh_tokens[0]) if jh_tokens else jh_norm
                candidate_full = f"{first_dim} {' '.join(jh_tokens[1:])}".strip() if len(jh_tokens) > 1 else first_dim

                target_client = client_by_name.get(jh_norm) or client_by_name.get(candidate_full)
                if target_client:
                    return EntityResolutionResult(
                        account_number=acc_num,
                        raw_holder=holder,
                        matched_household_id=target_client.get("household_id"),
                        matched_client_id=target_client.get("client_id"),
                        resolved_account_type="JOINT",
                        confidence=0.96,
                        resolution_method="JOINT_ACCOUNT_SPOUSAL_RESOLUTION",
                        reasoning=f"Joint account holder '{holder}' matched to client '{target_client.get('Name')}' in household."
                    )

        # 6. Surname Joint / Family Account (e.g. 'Thompson Joint')
        surname_joint_match = re.match(r"^(.*?)\s+(?:joint\s+wros|jtwros|joint|family)$", holder, re.IGNORECASE)
        if surname_joint_match:
            stem = surname_joint_match.group(1).strip().lower()
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

        # 7. LLM Disambiguation for Ambiguous / Complex Holdings
        # If deterministic rules did not yield high confidence, invoke Gemini reasoning
        try:
            candidates = [
                {"name": c.get("Name"), "household": c.get("household_id"), "segment": c.get("Segment")}
                for c in clients[:30]  # pass top candidate roster
            ]
            llm_prompt = (
                f"Custodian Account Holder: '{holder}'\n"
                f"Source Account Type: '{source_acc_type}'\n"
                f"Known Clients & Households: {json.dumps(candidates)}\n\n"
                f"Determine which client and household this account belongs to. "
                f"If there is a clear match (e.g. corporate LLC of client, initials, or married couple), "
                f"return the matching client name and confidence between 0.80 and 0.95. "
                f"If the holder cannot be matched confidently, set is_orphan=true and confidence < 0.50.\n"
                f"Return JSON strictly matching:\n"
                f'{{"matched_name": "...", "account_type": "...", "confidence": 0.90, "reasoning": "...", "is_orphan": false}}'
            )
            llm_resp = llm_client.generate_json(self.system_prompt, llm_prompt)
            matched_name = llm_resp.get("matched_name")
            matched_client = client_by_name.get(matched_name.lower()) if matched_name else None

            if matched_client and not llm_resp.get("is_orphan"):
                return EntityResolutionResult(
                    account_number=acc_num,
                    raw_holder=holder,
                    matched_household_id=matched_client.get("household_id"),
                    matched_client_id=matched_client.get("client_id"),
                    resolved_account_type=self._normalize_account_type(llm_resp.get("account_type", source_acc_type)),
                    confidence=float(llm_resp.get("confidence", 0.88)),
                    resolution_method="LLM_AGENT_DISAMBIGUATION",
                    reasoning=llm_resp.get("reasoning", f"LLM resolved '{holder}' to '{matched_name}'.")
                )
        except Exception as e:
            logger.debug("LLM entity disambiguation fallback for %s: %s", holder, e)

        # 8. Unmatched Orphan Account
        norm_type = self._normalize_account_type(source_acc_type)
        return EntityResolutionResult(
            account_number=acc_num,
            raw_holder=holder,
            matched_household_id=None,
            matched_client_id=None,
            resolved_account_type=norm_type,
            confidence=0.20,
            resolution_method="UNMAPPED_ORPHAN_ACCOUNT",
            reasoning=f"Account holder '{holder}' could not be matched with high confidence to any client or household in Notion CRM.",
            is_orphan=True,
        )

    def _normalize_account_type(self, raw_type: str) -> str:
        """Maps raw custodian account types to canonical enum."""
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
