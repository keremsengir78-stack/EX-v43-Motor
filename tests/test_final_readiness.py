import unittest
from ex_final_readiness import evaluate_final_readiness


class FinalReadinessTests(unittest.TestCase):
    def test_missing_inputs_block(self):
        result = evaluate_final_readiness(None)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ex_final_allowed"])
        self.assertIn("pipeline:missing", result["issues"])

    def test_metadata_ready_cannot_unlock_final(self):
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED",
             "externally_verified": True, "ex_final_allowed": True},
            {"status": "READY", "ex_final_allowed": True},
            {"status": "READY", "ex_final_allowed": True})
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["externally_verified"])
        self.assertFalse(result["ex_final_allowed"])
        self.assertIn("external_evidence:verification_not_implemented", result["issues"])

    def test_unavailable_calibration_blocks(self):
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            {"status": "BLOCKED"}, {"status": "READY"})
        self.assertIn("calibration:unavailable", result["issues"])

    def test_unavailable_historical_validation_blocks(self):
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            {"status": "READY"}, {"status": "BLOCKED"})
        self.assertIn("historical_validation:unavailable", result["issues"])


if __name__ == "__main__":
    unittest.main()
