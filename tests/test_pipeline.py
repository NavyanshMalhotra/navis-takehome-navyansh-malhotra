"""
End-to-End Pipeline Integration Tests.
Verifies pipeline execution, deliverable schemas, and structural invariants.
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

            # Structural invariants (not hardcoded to a specific run)
            self.assertGreater(len(data["households"]), 0)
            self.assertGreater(len(data["clients"]), 0)
            self.assertGreater(len(data["accounts"]), 0)
            self.assertGreater(len(data["advisors"]), 0)

            # Dual-metric AUM: active_aum <= total_mv (inactive households excluded)
            total_mv = sum(h["market_value_usd"] for h in data["households"] if h.get("market_value_usd") is not None)
            active_aum = sum(h["active_aum_usd"] for h in data["households"] if h.get("active_aum_usd") is not None)
            self.assertGreater(total_mv, 0)
            self.assertLessEqual(active_aum, total_mv, "Active AUM must not exceed total market value")

            # Provenance attached and uses relative paths
            for hh in data["households"]:
                self.assertIn("_provenance", hh)
                for k, prov in hh["_provenance"].items():
                    self.assertFalse(prov["source_file"].startswith("/Users/"), f"Absolute path: {prov['source_file']}")

            # Bill Fitzgerald should NOT be an orphan — must appear in canonical accounts
            fitzgerald_accounts = [a for a in data["accounts"] if "Fitzgerald" in a.get("account_holder_raw", "")]
            self.assertGreater(len(fitzgerald_accounts), 0, "Bill Fitzgerald must be resolved, not orphaned")

            # Carlos Vasquez and Priyanka Mehta are true orphans — must NOT appear
            acc_holders = [a["account_holder_raw"] for a in data["accounts"]]
            self.assertNotIn("Carlos Vasquez", acc_holders)
            self.assertNotIn("Priyanka Mehta", acc_holders)

        # 2. Check clarifications_round2.md
        clarif_path = config.outputs_dir / "clarifications_round2.md"
        self.assertTrue(clarif_path.exists())
        content = clarif_path.read_text(encoding="utf-8")
        self.assertTrue(any(lead in content for lead in (config.operations_lead, "Dana", "Operations")))
        self.assertIn("Trigger", content)
        self.assertIn("Evidence", content)
        self.assertNotIn("[Your Name]", content, "Template placeholder not replaced")

        # 3. Check knowledge SQLite cache exists
        db_path = config.outputs_dir / "knowledge_store.db"
        self.assertTrue(db_path.exists())

        # 4. Check OpenTelemetry traces recorded by swarm
        from pipeline.telemetry import telemetry
        summary = telemetry.get_summary()
        self.assertGreater(summary["total_spans"], 0, "Telemetry must record execution spans")
        self.assertGreater(summary["agent_invocations"], 0, "Telemetry must record agent invocations")
        self.assertIn("CanonicalTransformerAgent", summary["active_agents"])


if __name__ == "__main__":
    unittest.main()
