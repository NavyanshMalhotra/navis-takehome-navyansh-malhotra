"""
End-to-End Pipeline Integration Tests.
Verifies complete ReAct multi-agent execution, dual-metric AUM reconciliation,
deliverable schemas, and invariant audits.
"""

import unittest
import json
from pathlib import Path
from run_pipeline import run_pipeline
from config import config


class TestPipelineEndToEnd(unittest.TestCase):
    def test_pipeline_execution_and_artifacts(self):
        exit_code = run_pipeline()
        self.assertEqual(exit_code, 0, "Pipeline runner should exit with code 0")

        # 1. Check canonical_output.json exists and is valid
        canonical_path = config.outputs_dir / "canonical_output.json"
        self.assertTrue(canonical_path.exists())
        with open(canonical_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("households", data)
            self.assertIn("clients", data)
            self.assertIn("accounts", data)
            self.assertIn("advisors", data)
            self.assertIn("interactions", data)

            # Entity count assertions
            self.assertEqual(len(data["households"]), 52, "Expected 52 households")
            self.assertEqual(len(data["clients"]), 56, "Expected 56 clients (Petrov duplicate collapsed)")
            self.assertEqual(len(data["accounts"]), 50, "Expected 50 accounts (2 orphan accounts in triage)")
            self.assertEqual(len(data["advisors"]), 7, "Expected 7 advisors")
            self.assertEqual(len(data["interactions"]), 17, "Expected 17 interactions (Redwood Capital in triage)")

            # Dual-metric AUM validation
            total_mv = sum(h["market_value_usd"] for h in data["households"] if h.get("market_value_usd") is not None)
            active_aum = sum(h["active_aum_usd"] for h in data["households"] if h.get("active_aum_usd") is not None)
            
            self.assertAlmostEqual(total_mv, 66415625.00, places=2)
            self.assertAlmostEqual(active_aum, 66403225.00, places=2)
            self.assertAlmostEqual(total_mv - active_aum, 12400.00, places=2, msg="Delta must match Thompson churn exactly")

            # Assert provenance is attached to records and contains relative paths
            first_hh = data["households"][0]
            self.assertIn("_provenance", first_hh)
            self.assertTrue(len(first_hh["_provenance"]) > 0)
            for k, prov in first_hh["_provenance"].items():
                self.assertFalse(prov["source_file"].startswith("/Users/"), f"Found absolute path: {prov['source_file']}")

        # 2. Check clarifications_round2.md exists and contains expected sections
        clarif_path = config.outputs_dir / "clarifications_round2.md"
        self.assertTrue(clarif_path.exists())
        content = clarif_path.read_text(encoding="utf-8")
        self.assertTrue("Dana" in content, "Expected greeting addressed to Dana")
        self.assertIn("Trigger", content)

        self.assertIn("Evidence", content)
        self.assertIn("Proposed Default", content)
        self.assertIn("Carlos Vasquez", content)
        self.assertIn("Priyanka Mehta", content)
        self.assertIn("Redwood Capital", content)
        self.assertIn("Delgado", content)
        self.assertIn("Whitfield", content)
        self.assertIn("Petit", content)
        self.assertIn("Vandermeer", content)

        # 3. Check knowledge SQLite cache exists
        db_path = config.outputs_dir / "knowledge_store.db"
        self.assertTrue(db_path.exists(), "Local knowledge_store.db should be created")


if __name__ == "__main__":
    unittest.main()
