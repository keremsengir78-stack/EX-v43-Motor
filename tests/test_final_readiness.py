import unittest
from ex_final_readiness import evaluate_final_readiness


class FinalReadinessTests(unittest.TestCase):
    def test_missing_inputs_block(self):
        result = evaluate_final_readiness(None)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ex_final_allowed"])
        self.assertIn("pipeline:missing", result["issues"])

    def test_missing_checks_are_reported_individually(self):
        result = evaluate_final_readiness(None)
        self.assertEqual(set(result["missing_checks"]),
                         {"source_pipeline", "calibration",
                          "historical_validation", "external_evidence"})
        self.assertTrue(all(value is False for value in result["checks"].values()))

    def test_ready_metadata_still_reports_external_evidence_missing(self):
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            {"status": "READY"}, {"status": "READY"})
        self.assertEqual(result["missing_checks"], ["external_evidence"])
        self.assertFalse(result["ex_final_allowed"])

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
