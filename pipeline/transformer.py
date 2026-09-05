"""
Canonical Transformation & Normalization Engine.
Transforms source data into the 5 Nevis Canonical Entities:
1. Household
2. Client
3. Account
4. Advisor
5. Interaction
Strictly satisfies the 7 Nevis Canonical Rules and attaches granular field-level provenance.
"""

import re
from typing import Dict, List, Any, Optional, Tuple, Set
from pipeline.models import (
    Household, Client, Account, Advisor, Interaction,
    FieldProvenance, CanonicalOutputBundle, ClarificationItem
)
from pipeline.knowledge_layer import KnowledgeEngine
from pipeline.entity_resolver import EntityResolverAgent
from pipeline.doc_miner import DocMinerAgent
from config import config

class CanonicalTransformer:
    def __init__(self, knowledge_engine: KnowledgeEngine):
        self.ke = knowledge_engine
        self.entity_resolver = EntityResolverAgent()
        self.doc_miner = DocMinerAgent()

    def generate_id(self, prefix: str, raw_key: str) -> str:
        """Generates a stable, canonical slug ID."""
        clean = re.sub(r"[^a-zA-Z0-9]+", "-", raw_key.strip()).strip("-").upper()
        return f"{prefix}-{clean}"

    def transform_all(
        self,
        raw_advisors: List[Dict[str, Any]],
        raw_clients: List[Dict[str, Any]],
        raw_meetings: List[Dict[str, Any]],
        raw_custodian: List[Dict[str, Any]],
    ) -> Tuple[CanonicalOutputBundle, List[ClarificationItem]]:
        """
        Executes the end-to-end transformation.
        Returns: (canonical_bundle, clarifications_list)
        """
        # Extract prevailing As_Of_Date dynamically from custodian positions
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

        # Create quick lookup indices
        household_by_id = {h.household_id: h for h in households}
        client_by_name = {f"{c.first_name} {c.last_name}".lower(): c for c in clients}

        # 4. Transform Accounts & Rollup AUM
        accounts, account_clarifs = self._transform_accounts(
            raw_custodian, households, clients, client_notes, household_by_id
        )
        clarifications.extend(account_clarifs)

        # Compute Household AUM (Sum of accounts' market_value_usd, or None if no accounts)
        # Enforces Rule 2, Rule 3 (Unknown != zero), and Dana's Active AUM Rule
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
                # Dual-metric: active_aum_usd is market_value_usd if active, else 0.0
                hh.active_aum_usd = hh.market_value_usd if hh.is_active else 0.0
            else:
                # Rule 3: Unknown != zero. Household with no known accounts has AUM null, not 0.
                hh.market_value_usd = None
                hh.active_aum_usd = None

        # 5. Transform Interactions (Meetings)
        interactions, interaction_clarifs = self._transform_interactions(
            raw_meetings, meeting_notes, clients, households, advisors_by_name
        )
        clarifications.extend(interaction_clarifs)

        total_mv = round(sum(h.market_value_usd for h in households if h.market_value_usd is not None), 2)
        total_active = round(sum(h.active_aum_usd for h in households if h.active_aum_usd is not None), 2)

        # Bundle committed canonical entities
        bundle = CanonicalOutputBundle(
            households=households,
            clients=clients,
            accounts=accounts,
            advisors=list(advisors_by_id.values()),
            interactions=interactions,
            metadata={
                "target_firm": "Beaconcrest Advisors",
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
        """Maps advisor roster records into canonical Advisor entities."""
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
            # Also index initial format: e.g. "P. Raman" -> Priya Raman
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
        """
        Synthesizes households, normalizes client records, collapses duplicates,
        and flags unassigned advisors.
        """
        households: List[Household] = []
        clients: List[Client] = []
        clarifications: List[ClarificationItem] = []

        seen_households: Dict[str, Household] = {}
        processed_client_names: Set[str] = set()

        # Step A: Filter known duplicates (Petrov consolidation)
        deduped_raw_clients = []
        for rc in raw_clients:
            name = rc.get("Name", "").strip()
            if self.ke.is_known_duplicate_petrov(name):
                # Prefer standard 'Dmitri Petrov' entry
                if name.lower() == "petrov, dmitri":
                    continue
            deduped_raw_clients.append(rc)

        # Step B: Process each client
        for rc in deduped_raw_clients:
            name = rc.get("Name", "").strip()
            if not name:
                continue

            # Parse First & Last Name
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
            client_since = rc.get("Client Since", "").strip()
            source_file = self._clean_source_path(rc.get("_source_file", "sources/notion_export/Clients.csv"))
            source_row = rc.get("_source_row", "")

            # Check notes for insights
            insights = client_notes.get(name, {})

            # 1. Determine Household Name
            # e.g., Linda Chen has blank Household in CSV, but note says "Wife of Robert Chen — same household"
            hh_name = raw_hh
            hh_resolution_reason = "From Notion CSV 'Household' column"
            if not hh_name and insights.get("household_hint"):
                hh_name = insights["household_hint"]
                snip = insights["raw_snippets"][0] if insights.get("raw_snippets") else "CRM dossier notes"
                hh_resolution_reason = f"Derived from Notion markdown page body: '{snip}'"
            elif not hh_name:
                hh_name = f"{last_name} Household"
                hh_resolution_reason = f"Synthesized from client surname '{last_name}'"

            # Normalize household name for grouping (e.g. "Petrov" vs "Petrov Household")
            hh_slug = self.generate_id("HH", hh_name.replace("Household", "").strip())

            # 2. Determine Primary Advisor
            # Dana Rule: Advisor owns relationship. If blank, DO NOT guess from Service Rep.
            matched_advisor = advisors_by_name.get(raw_advisor.lower())
            advisor_id = matched_advisor.advisor_id if matched_advisor else None

            # 3. Status & Tags Normalization
            status, extra_tags, status_rule = self.ke.map_client_status(raw_status)
            source_tags = list(extra_tags)

            # Preserve business-meaningful unmapped CRM fields per Canonical Rule 6
            for col in ["Risk Profile", "Fee Schedule", "Segment", "Tags"]:
                val = rc.get(col, "").strip()
                if val:
                    source_tags.append(f"{col}: {val}")

            # 4. Check for unassigned advisor (Policy Gate: Dana Rule 2)
            if not advisor_id:
                # Flag to Dana in Round 2
                clarif_id = f"CLARIF-ADV-{hh_slug}"
                # Get unique active advisors from advisor roster (keyed by advisor_id)
                unique_advisors = list(advisors_by_id.values())
                proposed_default = "Marcus Webb (Advisor, Chicago)" if "Marcus" in raw_srep else "Priya Raman (Senior Advisor, San Francisco)"
                
                evidence_text = f"Notion Client row for '{name}'. Status='{raw_status}'. Service Rep='{raw_srep}'. Page note: '{insights.get('advisor_notes', 'None')}'."
                if self.ke.is_departed_staff(raw_srep):
                    evidence_text += f" WARNING: Service Rep '{raw_srep}' is Anna Novak who departed the firm."

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
                # For canonical compliance during staging, assign provisional or default ID
                advisor_id = "ADV-PENDING-CLARIFICATION"

            # 5. Create or Update Household
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
                            reasoning="Dana clarified Legacy means Harborline active book" if status_rule else "Standard status mapping"
                        )
                    }
                )
                seen_households[hh_slug] = hh
                households.append(hh)

            # 6. Determine Client Role (PRIMARY vs SPOUSE vs SIGNER vs OTHER)
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
        """
        Maps custodian position rows into canonical Account entities.
        Handles currency conversions and routes orphan accounts to clarifications.
        """
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

            # Resolve Account to Household & Client
            res = self.entity_resolver.resolve_account_to_household(
                r, hh_dicts, client_dicts, client_notes
            )

            # Check for Orphan Account (Canonical Rule 4)
            if res.is_orphan or not res.matched_household_id:
                clarif_id = f"CLARIF-ACC-{acc_num}"
                val_display = f"${float(raw_mv):,.2f} {currency}" if raw_mv else "N/A"
                clarifications.append(ClarificationItem(
                    id=clarif_id,
                    category="ORPHAN_ACCOUNT",
                    title=f"Unmapped Custodian Account — {holder} ({acc_num})",
                    trigger=f"Account '{acc_num}' at {custodian} ({val_display}) has holder '{holder}' with no matching client or household in Notion CRM.",
                    evidence=f"Custodian position record in {source_file}:Row {source_row}. Custodian={custodian}, Type={raw_acc_type}.",
                    candidate_options=[
                        f"Add '{holder}' as a new Household and Client in Nevis.",
                        f"Link to an existing client under a different legal name/entity.",
                        f"Account is closed, winding down, or belongs to another firm."
                    ],
                    proposed_default=f"Stage account under holding queue; request Dana confirm client identity or create Household '{holder.split()[-1]} Household'.",
                    confidence=0.20,
                    entity_ref=acc_num
                ))
                continue  # Rule 4: Do not include orphan accounts in committed canonical output

            # Parse Market Value & Convert Currency (Rule 5)
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
        """
        Maps Notion meetings to canonical Interaction entities.
        Enforces Canonical Rule 7 (every interaction rolls up to an existing household,
        no minting households from interactions, orphan interactions flagged).
        """
        interactions: List[Interaction] = []
        clarifications: List[ClarificationItem] = []

        client_to_hh = {f"{c.first_name} {c.last_name}".lower(): c.household_id for c in clients}
        # Inverted names index
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

            # 1. Resolve Client Field
            target_client_name = raw_client.lower()
            if notes.get("client_alias"):
                target_client_name = notes["client_alias"].lower()

            matched_hh_id = client_to_hh.get(target_client_name)

            # Check if this is an orphan interaction (Rule 7)
            if not matched_hh_id:
                clarif_id = f"CLARIF-INT-{self.generate_id('M', meet_name)}"
                clarifications.append(ClarificationItem(
                    id=clarif_id,
                    category="ORPHAN_INTERACTION",
                    title=f"Unmatched Interaction — '{meet_name}' ({raw_client})",
                    trigger=f"Meeting client '{raw_client}' cannot be resolved to any existing household in CRM. Canonical Rule 7 forbids minting new households from meetings.",
                    evidence=f"Meeting note: '{notes.get('raw_snippets', ['No notes'])[0]}'. Attendee='{attendee}'. Date='{raw_date}'.",
                    candidate_options=[
                        f"Lead became an active client under an unlisted name.",
                        f"Prospecting lead never converted; archive interaction in prospect lake.",
                        f"Typo/alias for an existing household."
                    ],
                    proposed_default=f"Archive interaction to prospect review queue without minting household pending Dana's confirmation.",
                    confidence=0.20,
                    entity_ref=meet_name
                ))
                continue  # Rule 7: Do not mint household; flag orphan interaction

            # 2. Normalize Interaction Type
            norm_type = "OTHER"
            t_upper = raw_type.upper()
            if "REVIEW" in t_upper or "QBR" in t_upper or "CHECK-IN" in t_upper:
                norm_type = "REVIEW"
            elif "PROSPECT" in t_upper or "INTRO" in t_upper or "DISCOVERY" in t_upper:
                norm_type = "PROSPECTING"
            elif "ONBOARD" in t_upper:
                norm_type = "ONBOARDING"

            # 3. Resolve Advisor Attendee
            matched_adv = advisors_by_name.get(attendee.lower())
            adv_id = matched_adv.advisor_id if matched_adv else None

            # 4. Standardize Date (e.g. 'June 12, 2025' -> '2025-06-12')
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
        """Converts prose dates (e.g. 'June 12, 2025') to ISO YYYY-MM-DD."""
        months = {
            "january": "01", "february": "02", "march": "03", "april": "04",
            "may": "05", "june": "06", "july": "07", "august": "08",
            "september": "09", "october": "10", "november": "11", "december": "12"
        }
        clean = prose_date.replace(",", "").strip()
        tokens = clean.split()
        if len(tokens) == 3:
            m, d, y = tokens[0].lower(), tokens[1], tokens[2]
            if m in months:
                return f"{y}-{months[m]}-{int(d):02d}"
        return prose_date
