import unittest

from ex_calibration_audit import audit_predictions


def row(i, probability=0.7, outcome=1):
    return {
        "fixture_id": "match-%d" % i,
        "market": "KG_VAR",
        "probability": probability,
        "outcome": outcome,
        "predicted_at": "2026-01-01T10:00:00Z",
        "kickoff_at": "2026-01-01T12:00:00Z",
        "settled_at": "2026-01-01T15:00:00Z",
    }


class CalibrationAuditTests(unittest.TestCase):
    def test_out_of_sample_brier_never_promotes_final(self):
        records = [row(i) for i in range(100)]
        result = audit_predictions(records, "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertAlmostEqual(result["brier_score"], 0.09)
        self.assertFalse(result["calibration_certified"])
        self.assertFalse(result["pup_allowed"])
        self.assertFalse(result["ex_final_allowed"])

    def test_insufficient_sample_is_blocked(self):
        result = audit_predictions([row(i) for i in range(30)], "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertIn("sample:insufficient", result["issues"])
        self.assertIsNone(result["brier_score"])

    def test_future_settlement_is_blocked(self):
        result = audit_predictions([row(1)], "KG_VAR", "2026-01-01T14:00:00Z")
        self.assertIn("record:0:temporal_leakage", result["issues"])

    def test_duplicate_fixture_is_blocked(self):
        result = audit_predictions([row(1), row(1)], "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertIn("record:1:duplicate_or_missing_fixture", result["issues"])

    def test_invalid_probability_and_boolean_outcome_are_blocked(self):
        for probability, outcome in ((float("nan"), 1), (1.2, 1), (True, 1), (0.5, True)):
            result = audit_predictions([row(1, probability, outcome)], "KG_VAR", "2026-02-01T00:00:00Z")
            self.assertIn("record:0:invalid_prediction_or_outcome", result["issues"])

    def test_wrong_market_is_blocked(self):
        result = audit_predictions([row(1)], "MS1", "2026-02-01T00:00:00Z")
        self.assertIn("record:0:market_mismatch", result["issues"])

    def test_no_time_travel_predictions(self):
        invalid = row(1)
        invalid["predicted_at"] = "2026-01-01T13:00:00Z"
        result = audit_predictions([invalid], "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertIn("record:0:temporal_leakage", result["issues"])


if __name__ == "__main__":
    unittest.main()
