"""
End-to-End Pipeline Integration Tests.
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

        # Check canonical_output.json exists and is valid
        canonical_path = config.outputs_dir / "canonical_output.json"
        self.assertTrue(canonical_path.exists())
        with open(canonical_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("households", data)
            self.assertIn("clients", data)
            self.assertIn("accounts", data)
            self.assertIn("advisors", data)
            self.assertIn("interactions", data)

            # Assert provenance is attached to records
            first_hh = data["households"][0]
            self.assertIn("_provenance", first_hh)
            self.assertTrue(len(first_hh["_provenance"]) > 0)

        # Check clarifications_round2.md exists and contains expected sections
        clarif_path = config.outputs_dir / "clarifications_round2.md"
        self.assertTrue(clarif_path.exists())
        content = clarif_path.read_text(encoding="utf-8")
        self.assertIn("Dana Ruiz", content)
        self.assertIn("Trigger", content)
        self.assertIn("Evidence", content)
        self.assertIn("Proposed Default", content)
        self.assertIn("Carlos Vasquez", content)
        self.assertIn("Priyanka Mehta", content)
        self.assertIn("Redwood Capital", content)
        self.assertIn("Delgado", content)

if __name__ == "__main__":
    unittest.main()
