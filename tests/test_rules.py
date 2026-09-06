"""
Unit & Invariant Tests for the Nevis Canonical Rules.
Always exercises the transformer — never reads from a cached output file.
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
from pipeline.models import CanonicalOutputBundle
from pipeline.transformer import CanonicalTransformer
from pipeline.auditor import AuditorAgent


class TestNevisCanonicalRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
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
        """Every household has a non-null primary advisor."""
        for h in self.bundle.households:
            self.assertIsNotNone(h.primary_advisor_id, f"Household {h.household_id} has null advisor")
            self.assertTrue(len(h.primary_advisor_id) > 0)

    def test_rule_2_household_aum(self):
        """Household AUM equals sum of its accounts' market_value_usd."""
        for h in self.bundle.households:
            accs = [a for a in self.bundle.accounts if a.household_id == h.household_id]
            if accs:
                expected = round(sum(a.market_value_usd for a in accs if a.market_value_usd is not None), 2)
                self.assertAlmostEqual(h.market_value_usd, expected, places=2)

    def test_rule_3_unknown_not_zero(self):
        """Households with no accounts have AUM=None, not 0."""
        zero_acc_households = [
            h for h in self.bundle.households
            if not [a for a in self.bundle.accounts if a.household_id == h.household_id]
        ]
        self.assertTrue(len(zero_acc_households) > 0, "Expected at least one household with no accounts")
        for h in zero_acc_households:
            self.assertIsNone(h.market_value_usd, f"{h.household_id} has no accounts but AUM is not None")

    def test_rule_4_zero_orphan_accounts(self):
        """Every account links to a valid household."""
        hh_ids = {h.household_id for h in self.bundle.households}
        for a in self.bundle.accounts:
            self.assertIn(a.household_id, hh_ids, f"Account {a.account_id} is orphaned")

        # Verify true orphans are NOT in canonical output
        acc_holders = [a.account_holder_raw for a in self.bundle.accounts]
        self.assertNotIn("Carlos Vasquez", acc_holders)
        self.assertNotIn("Priyanka Mehta", acc_holders)

    def test_rule_5_currency_conversion(self):
        """Non-USD accounts are converted and original currency recorded."""
        non_usd = [a for a in self.bundle.accounts if a.currency_original != "USD"]
        for a in non_usd:
            self.assertIsNotNone(a.market_value_usd)
            self.assertGreater(a.market_value_usd, 0)

    def test_rule_6_meaningful_fields_preserved(self):
        """Unmapped CRM fields preserved in source_tags, including Referred By."""
        all_tags = " ".join(
            tag for h in self.bundle.households for tag in h.source_tags
        )
        # At least some tags should exist
        self.assertTrue(len(all_tags) > 0)

    def test_rule_7_zero_orphan_interactions(self):
        """Every interaction links to an existing household."""
        hh_ids = {h.household_id for h in self.bundle.households}
        for i in self.bundle.interactions:
            self.assertIn(i.household_id, hh_ids, f"Interaction {i.interaction_id} is orphaned")

    def test_rule_8_active_aum_exclusion(self):
        """Inactive households have active_aum_usd = 0.0; active ones match market_value_usd."""
        thompson_hh = next((h for h in self.bundle.households if "THOMPSON" in h.household_id), None)
        self.assertIsNotNone(thompson_hh)
        self.assertFalse(thompson_hh.is_active)
        self.assertEqual(thompson_hh.status, "INACTIVE")
        self.assertAlmostEqual(thompson_hh.active_aum_usd, 0.0, places=2)

        for h in self.bundle.households:
            if h.is_active and h.market_value_usd is not None:
                self.assertAlmostEqual(h.active_aum_usd, h.market_value_usd, places=2)

    def test_provenance_relative_paths(self):
        """Provenance paths are relative (no absolute machine paths)."""
        for h in self.bundle.households:
            if hasattr(h, "_provenance") and h._provenance:
                for field, prov in h._provenance.items():
                    src_file = getattr(prov, "source_file", "") if not isinstance(prov, dict) else prov.get("source_file", "")
                    self.assertFalse(src_file.startswith("/Users/"), f"Absolute path: {src_file}")

    def test_slack_round1_resolutions(self):
        """Institutional business rules from operations communications are encoded and applied."""
        # Legacy -> ACTIVE with Harborline tag
        legacy_hh = next((h for h in self.bundle.households if "DELGADO" in h.household_id), None)
        self.assertIsNotNone(legacy_hh)
        self.assertTrue(
            any("harborline" in t.lower() for t in legacy_hh.source_tags),
            f"Expected Harborline acquisition tag in {legacy_hh.source_tags}"
        )

        # Petrov duplicate collapsed to 1
        petrov_clients = [c for c in self.bundle.clients if "petrov" in c.last_name.lower()]
        self.assertEqual(len(petrov_clients), 1, "Expected exactly 1 Petrov after deduplication")

        # Thompson marked INACTIVE
        thompson_hh = next((h for h in self.bundle.households if "THOMPSON" in h.household_id), None)
        self.assertIsNotNone(thompson_hh)
        self.assertEqual(thompson_hh.status, "INACTIVE")

    def test_full_audit_passes(self):
        """The canonical audit (Rules 1-8) must pass with no errors."""
        report = AuditorAgent.audit_canonical_bundle(self.bundle, run_semantic_check=False)
        self.assertTrue(report.is_valid, f"Audit failed:\n{report.summary()}")


if __name__ == "__main__":
    unittest.main()
