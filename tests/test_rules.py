"""
Unit & Invariant Tests for the 7 Nevis Canonical Rules.
"""

import unittest
from pathlib import Path
from config import config
from pipeline.readers import (
    read_advisor_roster,
    read_custodian_positions,
    read_notion_clients,
    read_notion_meetings
)
from pipeline.knowledge_layer import KnowledgeEngine
import json
from pipeline.models import CanonicalOutputBundle
from pipeline.transformer import CanonicalTransformer
from pipeline.auditor import CanonicalAuditor

class TestNevisCanonicalRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        canonical_path = config.outputs_dir / "canonical_output.json"
        if canonical_path.exists():
            with open(canonical_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cls.bundle = CanonicalOutputBundle.from_dict(data)
        else:
            cls.advisors = read_advisor_roster(config.sources_dir / "advisor_roster.csv")
            cls.custodian = read_custodian_positions(config.sources_dir / "custodian_positions.xlsx")
            cls.clients = read_notion_clients(config.sources_dir / "notion_export")
            cls.meetings = read_notion_meetings(config.sources_dir / "notion_export")
            cls.ke = KnowledgeEngine()
            cls.transformer = CanonicalTransformer(cls.ke)
            cls.bundle, cls.clarifs = cls.transformer.transform_all(
                cls.advisors, cls.clients, cls.meetings, cls.custodian
            )


    def test_rule_1_primary_advisor(self):
        """Rule 1: Exactly one primary advisor per household, non-null."""
        for h in self.bundle.households:
            self.assertIsNotNone(h.primary_advisor_id, f"Household {h.household_id} has null advisor")
            self.assertTrue(len(h.primary_advisor_id) > 0)

    def test_rule_2_household_aum(self):
        """Rule 2: Household AUM is sum of accounts market_value_usd."""
        for h in self.bundle.households:
            accs = [a for a in self.bundle.accounts if a.household_id == h.household_id]
            if accs:
                expected = round(sum(a.market_value_usd for a in accs), 2)
                self.assertAlmostEqual(h.market_value_usd, expected, places=2)

    def test_rule_3_unknown_not_zero(self):
        """Rule 3: Unknown != zero. A household with no known accounts has AUM null, not 0."""
        zero_acc_households = [
            h for h in self.bundle.households
            if not [a for a in self.bundle.accounts if a.household_id == h.household_id]
        ]
        self.assertTrue(len(zero_acc_households) > 0, "Expected at least one household with no accounts")
        for h in zero_acc_households:
            self.assertIsNone(h.market_value_usd, f"Household {h.household_id} has no accounts but AUM is not None")

    def test_rule_4_zero_orphan_accounts(self):
        """Rule 4: Every account rolls up to exactly one household. No orphan accounts."""
        hh_ids = {h.household_id for h in self.bundle.households}
        for a in self.bundle.accounts:
            self.assertIn(a.household_id, hh_ids, f"Account {a.account_id} is orphaned")

        # Verify Carlos Vasquez and Priyanka Mehta are NOT in canonical output
        acc_holders = [a.account_holder_raw for a in self.bundle.accounts]
        self.assertNotIn("Carlos Vasquez", acc_holders)
        self.assertNotIn("Priyanka Mehta", acc_holders)

    def test_rule_5_currency_conversion(self):
        """Rule 5: Non-USD source currencies converted to USD and original recorded."""
        al_rashid = next((a for a in self.bundle.accounts if "Al-Rashid" in a.account_holder_raw), None)
        self.assertIsNotNone(al_rashid)
        self.assertEqual(al_rashid.currency_original, "EUR")
        self.assertAlmostEqual(al_rashid.market_value_usd, 1875000 * 1.0710, places=2)

        bianchi = next((a for a in self.bundle.accounts if "Bianchi" in a.account_holder_raw), None)
        self.assertIsNotNone(bianchi)
        self.assertEqual(bianchi.currency_original, "CHF")
        self.assertAlmostEqual(bianchi.market_value_usd, 2100000 * 1.1140, places=2)

    def test_rule_6_meaningful_fields_preserved(self):
        """Rule 6: Fields with no first-class home preserved in source_tags."""
        chen = next((h for h in self.bundle.households if "CHEN" in h.household_id), None)
        self.assertIsNotNone(chen)
        tags_str = " ".join(chen.source_tags)
        self.assertTrue("Risk Profile" in tags_str or "Fee Schedule" in tags_str)

    def test_rule_7_zero_orphan_interactions(self):
        """Rule 7: Every interaction rolls up to an existing household. No orphan meetings."""
        hh_ids = {h.household_id for h in self.bundle.households}
        for i in self.bundle.interactions:
            self.assertIn(i.household_id, hh_ids, f"Interaction {i.interaction_id} is orphaned")

        # Verify Redwood Capital meeting was flagged in clarifications, not in canonical
        int_summaries = [i.summary for i in self.bundle.interactions]
        self.assertFalse(any("Redwood Capital" in str(s) for s in int_summaries))

    def test_rule_8_active_aum_exclusion(self):
        """Rule 8: Inactive households preserve custodian holdings but yield active_aum_usd = 0.0."""
        thompson_hh = next((h for h in self.bundle.households if "THOMPSON" in h.household_id), None)
        self.assertIsNotNone(thompson_hh)
        self.assertFalse(thompson_hh.is_active)
        self.assertEqual(thompson_hh.status, "INACTIVE")
        self.assertAlmostEqual(thompson_hh.market_value_usd, 12400.0, places=2)
        self.assertAlmostEqual(thompson_hh.active_aum_usd, 0.0, places=2)

        # Active households with accounts should have active_aum_usd == market_value_usd
        for h in self.bundle.households:
            if h.is_active and h.market_value_usd is not None:
                self.assertAlmostEqual(h.active_aum_usd, h.market_value_usd, places=2)

    def test_provenance_relative_paths(self):
        """Verify provenance paths are relative and clean (no absolute machine paths)."""
        for h in self.bundle.households:
            if hasattr(h, "_provenance") and h._provenance:
                for field, prov in h._provenance.items():
                    if isinstance(prov, dict):
                        src_file = prov.get("source_file", "")
                    else:
                        src_file = getattr(prov, "source_file", "")
                    self.assertFalse(src_file.startswith("/Users/"), f"Absolute path found in provenance: {src_file}")

    def test_slack_round1_resolutions(self):
        """Verify Dana's Slack Round 1 resolutions are strictly followed."""
        # 1. Legacy -> ACTIVE with Harborline tag
        legacy_hh = next((h for h in self.bundle.households if "DELGADO" in h.household_id), None)
        self.assertIsNotNone(legacy_hh)
        self.assertEqual(legacy_hh.status, "ACTIVE")
        self.assertIn("acquired from Harborline", legacy_hh.source_tags)

        # 2. Petrov duplicate collapsed
        petrov_clients = [c for c in self.bundle.clients if "petrov" in c.last_name.lower()]
        self.assertEqual(len(petrov_clients), 1, "Expected exactly 1 Petrov client after deduplication")

        # 3. Thompson marked INACTIVE
        thompson_hh = next((h for h in self.bundle.households if "THOMPSON" in h.household_id), None)
        self.assertIsNotNone(thompson_hh)
        self.assertEqual(thompson_hh.status, "INACTIVE")

if __name__ == "__main__":
    unittest.main()

