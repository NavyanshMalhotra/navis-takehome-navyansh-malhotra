"""
Canonical Transformation & Normalization Agent.
Transforms source data into the 5 Nevis Canonical Entities:
1. Household
2. Client
3. Account
4. Advisor
5. Interaction
Satisfies all 7 Canonical Rules and attaches granular field-level provenance.
"""

import re
from typing import Dict, List, Any, Optional, Tuple, Set

from google.adk.agents import BaseAgent
from pipeline.models import (
    Household, Client, Account, Advisor, Interaction,
    FieldProvenance, CanonicalOutputBundle, ClarificationItem
)
from pipeline.knowledge_layer import KnowledgeMiningAgent
from pipeline.entity_resolver import EntityResolverAgent
from pipeline.doc_miner import DossierMinerAgent
from pipeline.telemetry import telemetry
from config import config


class CanonicalTransformerAgent(BaseAgent):
    """Google ADK agent for canonical entity synthesis, lineage, and normalization."""

    name: str = "CanonicalTransformerAgent"
    description: str = "Synthesizes households and normalizes clients, accounts, advisors, and interactions."

    def __init__(self, knowledge_engine: Optional[KnowledgeMiningAgent] = None, **data):
        super().__init__(**data)
        ke = knowledge_engine or KnowledgeMiningAgent()
        object.__setattr__(self, "ke", ke)
        object.__setattr__(self, "entity_resolver", EntityResolverAgent())
        object.__setattr__(self, "doc_miner", DossierMinerAgent())

    def generate_id(self, prefix: str, raw_key: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9]+", "-", raw_key.strip()).strip("-").upper()
        return f"{prefix}-{clean}"

    def transform_all(
        self,
        raw_advisors: List[Dict[str, Any]],
        raw_clients: List[Dict[str, Any]],
        raw_meetings: List[Dict[str, Any]],
        raw_custodian: List[Dict[str, Any]],
    ) -> Tuple[CanonicalOutputBundle, List[ClarificationItem]]:
        with telemetry.trace_agent(self.name, task="transform_all"):
            # Extract prevailing As_Of_Date dynamically
            prevailing_as_of = "2025-06-30"
            for r in raw_custodian:
                if r.get("As_Of_Date"):
                    prevailing_as_of = str(r["As_Of_Date"]).strip()
                    break

            clarifications: List[ClarificationItem] = []

            # 1. Mine unstructured notes from Markdown pages
            client_notes = self.doc_miner.mine_client_notes(raw_clients)
            meeting_notes = self.doc_miner.mine_meeting_notes(raw_meetings)

            # 2. Transform Advisors
            advisors_by_id, advisors_by_name = self._transform_advisors(raw_advisors)

            # 3. Transform Clients and Synthesize Households
            households, clients, unassigned_advisor_clarifs = self._transform_households_and_clients(
                raw_clients, client_notes, advisors_by_id, advisors_by_name, prevailing_as_of
            )
            clarifications.extend(unassigned_advisor_clarifs)

            household_by_id = {h.household_id: h for h in households}

            # 4. Transform Accounts & Rollup AUM
            accounts, account_clarifs = self._transform_accounts(
                raw_custodian, households, clients, client_notes, household_by_id
            )
            clarifications.extend(account_clarifs)

            # Rollup AUM per household
            hh_account_totals: Dict[str, float] = {}
            hh_has_accounts: Set[str] = set()
            for acc in accounts:
                if acc.household_id in household_by_id:
                    hh_has_accounts.add(acc.household_id)
                    if acc.market_value_usd is not None:
                        hh_account_totals[acc.household_id] = hh_account_totals.get(acc.household_id, 0.0) + acc.market_value_usd

            for hh in households:
                hh.is_active = (hh.status == "ACTIVE")
                if hh.household_id in hh_has_accounts:
                    hh.market_value_usd = round(hh_account_totals.get(hh.household_id, 0.0), 2)
                    hh.active_aum_usd = hh.market_value_usd if hh.is_active else 0.0
                else:
                    # Rule 3: Unknown != zero
                    hh.market_value_usd = None
                    hh.active_aum_usd = None

            # 5. Transform Interactions (Meetings)
            interactions, interaction_clarifs = self._transform_interactions(
                raw_meetings, meeting_notes, clients, households, advisors_by_name
            )
            clarifications.extend(interaction_clarifs)

            total_mv = round(sum(h.market_value_usd for h in households if h.market_value_usd is not None), 2)
            total_active = round(sum(h.active_aum_usd for h in households if h.active_aum_usd is not None), 2)

            bundle = CanonicalOutputBundle(
                households=households,
                clients=clients,
                accounts=accounts,
                advisors=list(advisors_by_id.values()),
                interactions=interactions,
                metadata={
                    "target_firm": config.firm_name,
                    "onboarding_stage": "Round 2",
                    "as_of_date": prevailing_as_of,
                    "total_households": len(households),
                    "total_clients": len(clients),
                    "total_accounts": len(accounts),
                    "total_advisors": len(advisors_by_id),
                    "total_interactions": len(interactions),
                    "total_clarifications_flagged": len(clarifications),
                    "total_market_value_usd": total_mv,
                    "total_active_aum_usd": total_active,
                }
            )

            return bundle, clarifications

    def _clean_source_path(self, path_str: str) -> str:
        if not path_str:
            return ""
        s = str(path_str)
        base = str(config.base_dir)
        if s.startswith(base):
            return s[len(base):].lstrip("/")
        return s

    def _transform_advisors(self, raw_advisors: List[Dict[str, Any]]) -> Tuple[Dict[str, Advisor], Dict[str, Advisor]]:
        by_id = {}
        by_name = {}
        for r in raw_advisors:
            adv_id = r.get("advisor_id", "").strip()
            name = r.get("full_name", "").strip()
            role = r.get("role", "").strip()
            office = r.get("office", "").strip()
            source_file = self._clean_source_path(r.get("_source_file", "sources/advisor_roster.csv"))

            advisor = Advisor(
                advisor_id=adv_id,
                full_name=name,
                role=role,
                office=office,
                _provenance={
                    "advisor_id": FieldProvenance(
                        source_file=source_file,
                        source_location="Row",
                        source_raw_value=adv_id,
                        method="DETERMINISTIC_DIRECT",
                        confidence=1.0,
                        rule_or_agent="ROSTER_INGESTION"
                    ),
                    "full_name": FieldProvenance(
                        source_file=source_file,
                        source_location="Row",
                        source_raw_value=name,
                        method="DETERMINISTIC_DIRECT",
                        confidence=1.0,
                        rule_or_agent="ROSTER_INGESTION"
                    )
                }
            )
            by_id[adv_id] = advisor
            by_name[name.lower()] = advisor
            tokens = name.split()
            if len(tokens) >= 2:
                initial_alias = f"{tokens[0][0]}. {tokens[-1]}".lower()
                by_name[initial_alias] = advisor
        return by_id, by_name

    def _transform_households_and_clients(
        self,
        raw_clients: List[Dict[str, Any]],
        client_notes: Dict[str, Dict[str, Any]],
        advisors_by_id: Dict[str, Advisor],
        advisors_by_name: Dict[str, Advisor],
        prevailing_as_of: str = "2025-06-30"
    ) -> Tuple[List[Household], List[Client], List[ClarificationItem]]:
        households: List[Household] = []
        clients: List[Client] = []
        clarifications: List[ClarificationItem] = []

        seen_households: Dict[str, Household] = {}
        household_members: Dict[str, List[str]] = {}

        # Filter known duplicates using declarative deduplication rules
        deduped_raw_clients = []
        seen_dedup_entities: Set[str] = set()
        for rc in raw_clients:
            name = rc.get("Name", "").strip()
            dedup_rule = self.ke.find_deduplication_rule(name)
            if dedup_rule:
                target_entity = dedup_rule.metadata.get("entity_name", name)
                if target_entity in seen_dedup_entities:
                    continue
                seen_dedup_entities.add(target_entity)
            deduped_raw_clients.append(rc)

        for rc in deduped_raw_clients:
            name = rc.get("Name", "").strip()
            if not name:
                continue

            if "," in name:
                parts = [p.strip() for p in name.split(",", 1)]
                last_name, first_name = parts[0], parts[1]
            else:
                tokens = name.split()
                first_name = tokens[0] if tokens else ""
                last_name = " ".join(tokens[1:]) if len(tokens) > 1 else ""

            raw_status = rc.get("Status", "").strip()
            raw_advisor = rc.get("Advisor", "").strip()
            raw_srep = rc.get("Service Rep", "").strip()
            raw_hh = rc.get("Household", "").strip()
            source_file = self._clean_source_path(rc.get("_source_file", "sources/notion_export/Clients.csv"))
            source_row = rc.get("_source_row", "")

            insights = client_notes.get(name, {})

            # Determine Household Name with collision prevention
            hh_name = raw_hh
            hh_resolution_reason = "From Notion CSV 'Household' column"
            is_synthesized_surname = False

            if not hh_name and insights.get("household_hint"):
                hh_name = insights["household_hint"]
                snip = insights["raw_snippets"][0] if insights.get("raw_snippets") else "CRM dossier notes"
                hh_resolution_reason = f"Derived from Notion markdown page body: '{snip}'"
            elif not hh_name:
                hh_name = f"{last_name} Household"
                hh_resolution_reason = f"Synthesized from client surname '{last_name}'"
                is_synthesized_surname = True

            base_slug = self.generate_id("HH", hh_name.replace("Household", "").strip())
            hh_slug = base_slug

            # Collision prevention: if synthesized from surname alone and already seen, verify family link
            if is_synthesized_surname and hh_slug in seen_households:
                existing_members = household_members.get(hh_slug, [])
                is_linked = any(
                    insights.get("spouse_of", "").lower() in em.lower() or em.lower() in insights.get("spouse_of", "").lower()
                    for em in existing_members if insights.get("spouse_of")
                )
                if not is_linked and not any(last_name.lower() == em.split()[-1].lower() for em in existing_members):
                    hh_slug = f"{base_slug}-{self.generate_id('CLI', first_name)}"
                    hh_name = f"{first_name} {last_name} Household"

            household_members.setdefault(hh_slug, []).append(name)

            # Determine Primary Advisor
            matched_advisor = advisors_by_name.get(raw_advisor.lower())
            advisor_id = matched_advisor.advisor_id if matched_advisor else None

            # Status & Tags Normalization
            status, extra_tags, status_rule = self.ke.map_client_status(raw_status)
            source_tags = list(extra_tags)

            for col in ["Risk Profile", "Fee Schedule", "Segment", "Tags", "Referred By", "Client Since"]:
                val = rc.get(col, "").strip()
                if val:
                    source_tags.append(f"{col}: {val}")

            # Check unassigned advisor
            if not advisor_id:
                clarif_id = f"CLARIF-ADV-{hh_slug}"
                unique_advisors = list(advisors_by_id.values())

                srep_match = next((a for a in unique_advisors if a.full_name.lower() in raw_srep.lower() or raw_srep.lower() in a.full_name.lower()), None)
                if srep_match and not self.ke.is_departed_staff(srep_match.full_name):
                    proposed_default = f"{srep_match.full_name} ({srep_match.role}, {srep_match.office})"
                elif unique_advisors:
                    lead_adv = unique_advisors[0]
                    proposed_default = f"{lead_adv.full_name} ({lead_adv.role}, {lead_adv.office})"
                else:
                    proposed_default = "Assign primary advisor"

                evidence_text = f"Notion Client row for '{name}'. Status='{raw_status}'. Service Rep='{raw_srep}'. Page note: '{insights.get('advisor_notes', 'None')}'."
                if self.ke.is_departed_staff(raw_srep):
                    evidence_text += f" WARNING: Service Rep '{raw_srep}' is departed staff who left the firm."

                clarifications.append(ClarificationItem(
                    id=clarif_id,
                    category="UNASSIGNED_ADVISOR",
                    title=f"Unassigned Primary Advisor for Household '{hh_name}' ({name})",
                    trigger=f"Advisor field is blank in Notion CRM for '{name}'. Canonical Rule 1 requires exactly one non-null primary advisor.",
                    evidence=evidence_text,
                    candidate_options=[
                        f"Assign to {adv.full_name} ({adv.office})" for adv in unique_advisors[:3]
                    ],
                    proposed_default=f"Assign to {proposed_default}",
                    confidence=0.40,
                    entity_ref=hh_slug
                ))
                advisor_id = "ADV-PENDING-CLARIFICATION"

            # Create or update Household
            if hh_slug not in seen_households:
                hh = Household(
                    household_id=hh_slug,
                    household_name=hh_name if "Household" in hh_name else f"{hh_name} Household",
                    primary_advisor_id=advisor_id,
                    status=status,
                    as_of_date=prevailing_as_of,
                    source_tags=source_tags,
                    _provenance={
                        "household_id": FieldProvenance(
                            source_file=source_file,
                            source_location=f"Row {source_row}",
                            source_raw_value=raw_hh,
                            method="SYNTHESIZED_SLUG",
                            confidence=1.0,
                            rule_or_agent="HOUSEHOLD_SYNTHESIS",
                            reasoning=hh_resolution_reason
                        ),
                        "primary_advisor_id": FieldProvenance(
                            source_file=source_file,
                            source_location=f"Row {source_row}",
                            source_raw_value=raw_advisor,
                            method="ROSTER_LOOKUP" if matched_advisor else "FLAGGED_UNASSIGNED",
                            confidence=1.0 if matched_advisor else 0.40,
                            rule_or_agent="RULE_ADVISOR_PRECEDENCE",
                            reasoning=f"Matched advisor '{raw_advisor}' to roster ID {advisor_id}" if matched_advisor else "Blank advisor flagged per Dana Ruiz"
                        ),
                        "status": FieldProvenance(
                            source_file=source_file,
                            source_location=f"Row {source_row}",
                            source_raw_value=raw_status,
                            method="RULE_ENGINE" if status_rule else "DETERMINISTIC_DIRECT",
                            confidence=1.0,
                            rule_or_agent=status_rule.rule_id if status_rule else "STATUS_NORMALIZATION",
                            reasoning=status_rule.description if status_rule else "Standard status mapping"
                        )
                    }
                )
                seen_households[hh_slug] = hh
                households.append(hh)

            # Determine Client Role
            role = "PRIMARY"
            role_reasoning = "Primary contact for household"
            if insights.get("role") and insights["role"] not in ("PRIMARY", ""):
                role = insights["role"]
                role_reasoning = f"Derived from Notion notes: role is '{role}'"
            elif insights.get("spouse_of"):
                role = "SPOUSE"
                role_reasoning = f"Identified as spouse/wife of '{insights['spouse_of']}' from Notion page body"

            client_id = self.generate_id("CLI", name)
            client = Client(
                client_id=client_id,
                household_id=hh_slug,
                first_name=first_name,
                last_name=last_name,
                role=role,
                source_tags=source_tags,
                _provenance={
                    "client_id": FieldProvenance(
                        source_file=source_file,
                        source_location=f"Row {source_row}",
                        source_raw_value=name,
                        method="CANONICAL_ID_GEN",
                        confidence=1.0,
                        rule_or_agent="CLIENT_INGESTION"
                    ),
                    "role": FieldProvenance(
                        source_file=rc.get("_page_file") or source_file,
                        source_location="Page Body / Row",
                        source_raw_value=name,
                        method="LLM_DOC_MINING" if insights.get("spouse_of") else "DEFAULT_PRIMARY",
                        confidence=0.98 if insights.get("spouse_of") else 0.90,
                        rule_or_agent="ROLE_ASSIGNMENT",
                        reasoning=role_reasoning
                    )
                }
            )
            clients.append(client)

        return households, clients, clarifications

    def _transform_accounts(
        self,
        raw_custodian: List[Dict[str, Any]],
        households: List[Household],
        clients: List[Client],
        client_notes: Dict[str, Any],
        household_by_id: Dict[str, Household]
    ) -> Tuple[List[Account], List[ClarificationItem]]:
        accounts: List[Account] = []
        clarifications: List[ClarificationItem] = []

        hh_dicts = [h.to_dict() for h in households]
        client_dicts = [c.to_dict() for c in clients]
        for cd in client_dicts:
            cd["Name"] = f"{cd['first_name']} {cd['last_name']}".strip()

        for r in raw_custodian:
            acc_num = r.get("Account_Number", "").strip()
            holder = r.get("Account_Holder", "").strip()
            raw_acc_type = r.get("Account_Type", "").strip()
            raw_mv = r.get("Market_Value", "").strip()
            currency = r.get("Currency", "USD").strip()
            as_of = r.get("As_Of_Date", "2025-06-30").strip()
            custodian = r.get("Custodian", "Schwab").strip()
            source_file = self._clean_source_path(r.get("_source_file", "sources/custodian_positions.xlsx"))
            source_row = r.get("_source_row", "")

            res = self.entity_resolver.resolve_account_to_household(
                r, hh_dicts, client_dicts, client_notes
            )

            # Confidence routing against config thresholds
            if res.is_orphan or not res.matched_household_id or res.confidence < config.confidence_low_threshold:
                clarif_id = f"CLARIF-ACC-{acc_num}"
                val_display = f"${float(raw_mv):,.2f} {currency}" if raw_mv else "N/A"
                clarifications.append(ClarificationItem(
                    id=clarif_id,
                    category="ORPHAN_ACCOUNT",
                    title=f"Unmapped Custodian Account — {holder} ({acc_num})",
                    trigger=f"Account '{acc_num}' at {custodian} ({val_display}) has holder '{holder}' with no matching client or household in Notion CRM. Confidence: {res.confidence:.2f}.",
                    evidence=f"Custodian record in {source_file}:Row {source_row}. Custodian={custodian}, Type={raw_acc_type}. Method={res.resolution_method}.",
                    candidate_options=[
                        f"Add '{holder}' as a new Household and Client in Nevis.",
                        f"Link to an existing client under a different legal name/entity.",
                        f"Account is closed, winding down, or belongs to another firm."
                    ],
                    proposed_default=f"Stage account under holding queue; request Dana confirm client identity or create Household '{holder.split()[-1]} Household'.",
                    confidence=res.confidence,
                    entity_ref=acc_num
                ))
                continue

            market_val_num = float(raw_mv) if raw_mv else 0.0
            usd_val, fx_rate, fx_reason = self.ke.convert_currency_to_usd(currency, market_val_num)

            acc_id = self.generate_id("ACC", acc_num)
            account = Account(
                account_id=acc_id,
                household_id=res.matched_household_id,
                account_type=res.resolved_account_type,
                market_value_usd=usd_val,
                currency_original=currency,
                as_of_date=as_of,
                custodian=custodian,
                account_holder_raw=holder,
                _provenance={
                    "account_id": FieldProvenance(
                        source_file=source_file,
                        source_location=f"Row {source_row}",
                        source_raw_value=acc_num,
                        method="CANONICAL_ID_GEN",
                        confidence=1.0,
                        rule_or_agent="CUSTODIAN_INGESTION"
                    ),
                    "household_id": FieldProvenance(
                        source_file=source_file,
                        source_location=f"Row {source_row}",
                        source_raw_value=holder,
                        method=res.resolution_method,
                        confidence=res.confidence,
                        rule_or_agent="ENTITY_RESOLVER_AGENT",
                        reasoning=res.reasoning
                    ),
                    "market_value_usd": FieldProvenance(
                        source_file=source_file,
                        source_location=f"Row {source_row}",
                        source_raw_value=raw_mv,
                        method="CURRENCY_CONVERSION" if currency != "USD" else "DETERMINISTIC_DIRECT",
                        confidence=1.0,
                        rule_or_agent="RULE_FOREIGN_CURRENCY_USD_REPORTING" if currency != "USD" else "DIRECT_BALANCE",
                        reasoning=fx_reason if currency != "USD" else "USD market value direct from custodian"
                    )
                }
            )
            accounts.append(account)

        return accounts, clarifications

    def _transform_interactions(
        self,
        raw_meetings: List[Dict[str, Any]],
        meeting_notes: Dict[str, Dict[str, Any]],
        clients: List[Client],
        households: List[Household],
        advisors_by_name: Dict[str, Advisor]
    ) -> Tuple[List[Interaction], List[ClarificationItem]]:
        interactions: List[Interaction] = []
        clarifications: List[ClarificationItem] = []

        client_to_hh = {f"{c.first_name} {c.last_name}".lower(): c.household_id for c in clients}
        for c in clients:
            client_to_hh[f"{c.last_name}, {c.first_name}".lower()] = c.household_id

        for rm in raw_meetings:
            meet_name = rm.get("Name", "").strip()
            raw_client = rm.get("Client", "").strip()
            raw_type = rm.get("Type", "").strip()
            raw_date = rm.get("Date", "").strip()
            attendee = rm.get("Attendee", "").strip()
            source_file = self._clean_source_path(rm.get("_source_file", "sources/notion_export/Meetings.csv"))
            source_row = rm.get("_source_row", "")

            notes = meeting_notes.get(meet_name, {})

            target_client_name = raw_client.lower()
            if notes.get("client_alias"):
                target_client_name = notes["client_alias"].lower()

            matched_hh_id = client_to_hh.get(target_client_name)
            if not matched_hh_id:
                # Deterministic diminutive alias fallback (e.g. 'Bob Chen' -> 'Robert Chen')
                raw_tokens = raw_client.split()
                if len(raw_tokens) >= 2:
                    raw_first, raw_last = raw_tokens[0], raw_tokens[-1]
                    for c in clients:
                        if c.last_name.lower() == raw_last.lower() and self.entity_resolver.is_diminutive_or_alias(raw_first, c.first_name):
                            matched_hh_id = c.household_id
                            notes["client_alias"] = f"{c.first_name} {c.last_name}"
                            break

            if not matched_hh_id:
                clarif_id = f"CLARIF-INT-{self.generate_id('M', meet_name)}"
                snip_text = notes["raw_snippets"][0] if notes.get("raw_snippets") else "No notes"
                clarifications.append(ClarificationItem(
                    id=clarif_id,
                    category="ORPHAN_INTERACTION",
                    title=f"Unmatched Interaction — '{meet_name}' ({raw_client})",
                    trigger=f"Meeting client '{raw_client}' cannot be resolved to any existing household in CRM. Canonical Rule 7 forbids minting new households from meetings.",
                    evidence=f"Meeting note: '{snip_text}'. Attendee='{attendee}'. Date='{raw_date}'.",
                    candidate_options=[
                        "Lead became an active client under an unlisted name.",
                        "Prospecting lead never converted; archive interaction in prospect lake.",
                        "Typo/alias for an existing household."
                    ],
                    proposed_default="Archive interaction to prospect review queue without minting household pending Dana's confirmation.",
                    confidence=0.20,
                    entity_ref=meet_name
                ))
                continue

            norm_type = "OTHER"
            t_upper = raw_type.upper()
            if "REVIEW" in t_upper or "QBR" in t_upper or "CHECK-IN" in t_upper:
                norm_type = "REVIEW"
            elif "PROSPECT" in t_upper or "INTRO" in t_upper or "DISCOVERY" in t_upper:
                norm_type = "PROSPECTING"
            elif "ONBOARD" in t_upper:
                norm_type = "ONBOARDING"

            matched_adv = advisors_by_name.get(attendee.lower())
            adv_id = matched_adv.advisor_id if matched_adv else None
            standard_date = self._parse_prose_date(raw_date)

            int_id = self.generate_id("INT", meet_name)
            interaction = Interaction(
                interaction_id=int_id,
                household_id=matched_hh_id,
                interaction_type=norm_type,
                interaction_date=standard_date,
                advisor_id=adv_id,
                summary=notes.get("summary") or f"Meeting with {raw_client} ({raw_type})",
                attendee_raw=attendee,
                _provenance={
                    "interaction_id": FieldProvenance(
                        source_file=source_file,
                        source_location=f"Row {source_row}",
                        source_raw_value=meet_name,
                        method="CANONICAL_ID_GEN",
                        confidence=1.0,
                        rule_or_agent="MEETING_INGESTION"
                    ),
                    "household_id": FieldProvenance(
                        source_file=source_file,
                        source_location=f"Row {source_row}",
                        source_raw_value=raw_client,
                        method="ALIAS_RESOLVER" if notes.get("client_alias") else "CLIENT_HOUSEHOLD_FK",
                        confidence=0.98 if notes.get("client_alias") else 1.0,
                        rule_or_agent="INTERACTION_HOUSEHOLD_RESOLVER",
                        reasoning=f"Resolved '{raw_client}' -> '{notes.get('client_alias')}' -> Household {matched_hh_id}" if notes.get("client_alias") else f"Direct link to household {matched_hh_id}"
                    )
                }
            )
            interactions.append(interaction)

        return interactions, clarifications

    def _parse_prose_date(self, prose_date: str) -> str:
        from datetime import datetime
        if not prose_date:
            return ""
        clean = prose_date.replace(",", "").strip()
        for fmt in ("%B %d %Y", "%b %d %Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                dt = datetime.strptime(clean, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return prose_date


# Backward compatibility alias
CanonicalTransformer = CanonicalTransformerAgent
