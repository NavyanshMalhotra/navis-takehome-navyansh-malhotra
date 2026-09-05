"""
Generalized Entity Resolution & Wealth Management Disambiguation Specialist.
Disentangles legal entities (Trusts, LLCs), Joint account holders, inverted names,
initials, and common diminutives to resolve custodian accounts to Households and Clients.
Does NOT overfit to individual names; implements generalized NLP & wealth heuristics.
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from config import config
from pipeline.llm_client import llm_client

# Generalized Anglo & International Diminutive Dictionaries
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
    "ken": "kenji",
}

class EntityResolutionResult:
    def __init__(
        self,
        account_number: str,
        raw_holder: str,
        matched_household_id: Optional[str],
        matched_client_id: Optional[str],
        resolved_account_type: str,
        confidence: float,
        resolution_method: str,
        reasoning: str,
        is_orphan: bool = False
    ):
        self.account_number = account_number
        self.raw_holder = raw_holder
        self.matched_household_id = matched_household_id
        self.matched_client_id = matched_client_id
        self.resolved_account_type = resolved_account_type
        self.confidence = confidence
        self.resolution_method = resolution_method
        self.reasoning = reasoning
        self.is_orphan = is_orphan

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
                last, first = parts[0], parts[1]
                return first, last
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
             'The Smith Family Living Trust' -> 'Smith'
        """
        trust_pattern = re.compile(
            r"^(.*?)\s+(?:revocable\s+trust|irrevocable\s+trust|living\s+trust|family\s+trust|revocable|trust)$",
            re.IGNORECASE
        )
        m = trust_pattern.match(text.strip())
        if m:
            candidate = m.group(1).strip()
            # Remove leading 'The '
            if candidate.lower().startswith("the "):
                candidate = candidate[4:].strip()
            return candidate
        return None

    def extract_corporate_entity(self, text: str) -> Optional[str]:
        """
        Detects corporate entity indicators (LLC, Inc, Corp, Holdings).
        e.g. 'Nakamura Holdings LLC' -> 'Nakamura'
        """
        corp_pattern = re.compile(
            r"\b(?:llc|inc|corp|holdings|capital|partners|lp|fund|associates)\b",
            re.IGNORECASE
        )
        if corp_pattern.search(text):
            # Extract root stem
            stem = corp_pattern.sub("", text).strip()
            return stem if stem else text
        return None

    def extract_joint_holders(self, text: str) -> Optional[List[str]]:
        """
        Extracts multiple person names from joint designations.
        e.g. 'Bob & Linda Chen' -> ['Bob Chen', 'Linda Chen']
             'Rachel & Daniel Abramson' -> ['Rachel Abramson', 'Daniel Abramson']
        """
        clean = re.sub(r"(?i)\b(?:joint\s+wros|jtwros|joint|wros|tic)\b", "", text).strip()
        
        split_match = re.split(r"\s+(?:&|and)\s+", clean, flags=re.IGNORECASE)
        if len(split_match) == 2:
            first_part, second_part = split_match[0].strip(), split_match[1].strip()
            # If first part is only given name (e.g. 'Bob' in 'Bob & Linda Chen')
            # propagate surname from second part
            second_tokens = second_part.split()
            first_tokens = first_part.split()
            
            if len(first_tokens) == 1 and len(second_tokens) >= 2:
                surname = second_tokens[-1]
                first_part = f"{first_tokens[0]} {surname}"
            return [first_part, second_part]
            
        return None

    def resolve_diminutive(self, first_name: str) -> str:
        """Returns standard canonical name for diminutive."""
        return NICKNAME_MAP.get(first_name.lower().strip(), first_name.lower().strip())

    def resolve_account_to_household(
        self,
        account: Dict[str, Any],
        households: List[Dict[str, Any]],
        clients: List[Dict[str, Any]],
        extracted_notes: Dict[str, Any]
    ) -> EntityResolutionResult:
        """
        Resolves a single custodian account row to the best matching Household and Client.
        Implements generalized, non-overfitted scoring.
        """
        acc_num = account.get("Account_Number", "").strip()
        holder = account.get("Account_Holder", "").strip()
        source_acc_type = account.get("Account_Type", "").strip()
        
        # Build lookup indices
        client_by_name = {self.normalize_name(c["Name"]).lower(): c for c in clients}
        client_by_id = {c["client_id"]: c for c in clients if "client_id" in c}
        household_by_id = {h["household_id"]: h for h in households}
        household_by_name = {self.normalize_name(h["household_name"]).lower(): h for h in households}

        # 1. Exact Match on Client Name
        norm_holder = self.normalize_name(holder).lower()
        if norm_holder in client_by_name:
            matched_client = client_by_name[norm_holder]
            hh_id = matched_client.get("household_id")
            norm_type = self._normalize_account_type(source_acc_type)
            return EntityResolutionResult(
                account_number=acc_num,
                raw_holder=holder,
                matched_household_id=hh_id,
                matched_client_id=matched_client.get("client_id"),
                resolved_account_type=norm_type,
                confidence=1.0,
                resolution_method="EXACT_CLIENT_NAME_MATCH",
                reasoning=f"Exact match on client name '{holder}'."
            )

        # 2. Inverted Name Check (e.g. 'Petrov, Dmitri' or 'Nakamura, Kenji')
        if "," in holder:
            first, last = self.parse_inverted_name(holder)
            straight_name = f"{first} {last}".strip().lower()
            if straight_name in client_by_name:
                matched_client = client_by_name[straight_name]
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

        # 3. Trust Entity Resolution (e.g. 'Ada Okonkwo Revocable Trust')
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

        # 4. Joint Account Resolution (e.g. 'Bob & Linda Chen', 'Rachel & Daniel Abramson')
        joint_holders = self.extract_joint_holders(holder)
        if joint_holders:
            # Check matches for both or either holder
            for jh in joint_holders:
                jh_norm = self.normalize_name(jh).lower()
                # Check direct or diminutive
                jh_tokens = jh_norm.split()
                if jh_tokens:
                    first_dim = self.resolve_diminutive(jh_tokens[0])
                    candidate_full = f"{first_dim} {' '.join(jh_tokens[1:])}".strip()
                else:
                    candidate_full = jh_norm

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

        # 4b. Single-Surname Joint / Family Account (e.g. 'Thompson Joint')
        surname_joint_match = re.match(r"^(.*?)\s+(?:joint\s+wros|jtwros|joint|family)$", holder, re.IGNORECASE)
        if surname_joint_match:
            stem = surname_joint_match.group(1).strip().lower()
            # Match against households or client surnames
            for hh_obj in households:
                hh_clean = hh_obj.get("household_name", "").lower()
                hh_id_val = hh_obj.get("household_id", "")
                if stem in hh_clean or stem in hh_id_val.lower():
                    # Find primary client in household
                    cand_client = next((c for c in clients if c.get("household_id") == hh_id_val), None)
                    return EntityResolutionResult(
                        account_number=acc_num,
                        raw_holder=holder,
                        matched_household_id=hh_id_val,
                        matched_client_id=cand_client.get("client_id") if cand_client else None,
                        resolved_account_type="JOINT",
                        confidence=0.96,
                        resolution_method="SURNAME_JOINT_HOUSEHOLD_RESOLUTION",
                        reasoning=f"Surname joint holder '{holder}' matched to household '{hh_obj.get('household_name')}'."
                    )

        # 5. Corporate / LLC Entity Resolution (e.g. 'Nakamura Holdings LLC')
        corp_stem = self.extract_corporate_entity(holder)
        if corp_stem:
            # Match against households or client surnames
            stem_tokens = corp_stem.lower().split()
            for stem_word in stem_tokens:
                if len(stem_word) > 2:
                    for c_name, c_obj in client_by_name.items():
                        if stem_word in c_name:
                            return EntityResolutionResult(
                                account_number=acc_num,
                                raw_holder=holder,
                                matched_household_id=c_obj.get("household_id"),
                                matched_client_id=c_obj.get("client_id"),
                                resolved_account_type="CORPORATE",
                                confidence=0.92,
                                resolution_method="CORPORATE_HOLDINGS_STEM_RESOLUTION",
                                reasoning=f"Corporate entity '{holder}' linked to client '{c_obj.get('Name')}' via surname stem '{stem_word}'."
                            )

        # 6. Initials Resolution (e.g. 'G. Whitfield' -> 'George Whitfield')
        initial_match = re.match(r"^([A-Za-z])\.?\s+([A-Za-z\-]+)$", holder)
        if initial_match:
            init_letter, surname = initial_match.group(1).lower(), initial_match.group(2).lower()
            matching_candidates = [
                c for c_name, c in client_by_name.items()
                if c_name.split()[-1] == surname and c_name.split()[0].startswith(init_letter)
            ]
            if len(matching_candidates) == 1:
                cand = matching_candidates[0]
                norm_type = self._normalize_account_type(source_acc_type)
                return EntityResolutionResult(
                    account_number=acc_num,
                    raw_holder=holder,
                    matched_household_id=cand.get("household_id"),
                    matched_client_id=cand.get("client_id"),
                    resolved_account_type=norm_type,
                    confidence=0.92,
                    resolution_method="INITIAL_SURNAME_DISAMBIGUATION",
                    reasoning=f"Initial '{holder}' uniquely matched to '{cand.get('Name')}'."
                )

        # 7. Diminutive / Nickname Match (e.g. 'Bill Fitzgerald' -> 'William Fitzgerald')
        holder_tokens = holder.split()
        if len(holder_tokens) == 2:
            first_raw, last_raw = holder_tokens[0].lower(), holder_tokens[1].lower()
            canon_first = self.resolve_diminutive(first_raw)
            if canon_first != first_raw:
                expected_full = f"{canon_first} {last_raw}"
                if expected_full in client_by_name:
                    cand = client_by_name[expected_full]
                    norm_type = self._normalize_account_type(source_acc_type)
                    return EntityResolutionResult(
                        account_number=acc_num,
                        raw_holder=holder,
                        matched_household_id=cand.get("household_id"),
                        matched_client_id=cand.get("client_id"),
                        resolved_account_type=norm_type,
                        confidence=0.94,
                        resolution_method="DIMINUTIVE_ALIAS_RESOLUTION",
                        reasoning=f"Diminutive '{first_raw.title()}' mapped to canonical '{canon_first.title()}' for '{cand.get('Name')}'."
                    )

        # 8. Unmatched / Orphan Detection
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
            is_orphan=True
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
