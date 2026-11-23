"""Fail-closed regression checks for EX calibration audit.

Run: python -m unittest test_ex_calibration_safety.py
These checks do not authorize EX FINAL or certify probabilities.
"""
import unittest

from ex_calibration_audit import audit_predictions


def sample(fixture_id="fixture-1", probability=0.65, outcome=1,
           predicted_at="2026-10-01T10:00:00Z",
           kickoff_at="2026-10-01T12:00:00Z",
           settled_at="2026-10-01T14:00:00Z"):
    return {
        "fixture_id": fixture_id,
        "market": "KG_VAR",
        "probability": probability,
        "outcome": outcome,
        "predicted_at": predicted_at,
        "kickoff_at": kickoff_at,
        "settled_at": settled_at,
    }


class CalibrationSafetyTests(unittest.TestCase):
    def check_blocked(self, records, **kwargs):
        result = audit_predictions(
            records, "KG_VAR", "2026-10-02T00:00:00Z",
            min_samples=30, **kwargs
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["brier_score"])
        self.assertFalse(result["calibration_certified"])
        self.assertFalse(result["pup_allowed"])
        self.assertFalse(result["ex_final_allowed"])
        return result

    def test_duplicate_fixture_with_surrounding_spaces(self):
        result = self.check_blocked([
            sample("fixture-1"), sample(" fixture-1 ")
        ])
        self.assertTrue(any("duplicate_or_missing_fixture" in x
                            for x in result["issues"]))

    def test_prediction_after_kickoff(self):
        result = self.check_blocked([
            sample(predicted_at="2026-10-01T13:00:00Z")
        ])
        self.assertTrue(any("temporal_leakage" in x
                            for x in result["issues"]))

    def test_unsettled_at_cutoff(self):
        result = self.check_blocked([
            sample(settled_at="2026-10-02T00:00:00Z")
        ])
        self.assertTrue(any("temporal_leakage" in x
                            for x in result["issues"]))

    def test_invalid_probability_is_rejected(self):
        result = self.check_blocked([sample(probability=float("nan"))])
        self.assertTrue(any("invalid_prediction_or_outcome" in x
                            for x in result["issues"]))

    def test_valid_historical_sample_is_not_certified(self):
        records = [sample(fixture_id="fixture-%d" % i) for i in range(30)]
        result = audit_predictions(
            records, "KG_VAR", "2026-10-02T00:00:00Z", min_samples=30
        )
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertEqual(result["sample_size"], 30)
        self.assertFalse(result["calibration_certified"])
        self.assertFalse(result["pup_allowed"])
        self.assertFalse(result["ex_final_allowed"])

    def test_unsupported_market_fails_closed(self):
        result = audit_predictions([sample()], "UNKNOWN", "2026-10-02T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("market:unsupported", result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_boolean_minimum_sample_is_invalid(self):
        result = audit_predictions([sample()], "KG_VAR", "2026-10-02T00:00:00Z",
                                   min_samples=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("min_samples:invalid", result["issues"])
        self.assertFalse(result["calibration_certified"])

    def test_cutoff_equal_settlement_is_blocked(self):
        result = audit_predictions([sample(settled_at="2026-10-02T00:00:00Z")],
                                   "KG_VAR", "2026-10-02T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("temporal_leakage" in issue for issue in result["issues"]))

    def test_valid_boundary_probabilities_are_not_certified(self):
        records = [sample(fixture_id="boundary-%d" % i,
                          probability=float(i % 2), outcome=i % 2)
                   for i in range(30)]
        result = audit_predictions(records, "KG_VAR", "2026-10-02T00:00:00Z",
                                   min_samples=30)
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertEqual(result["brier_score"], 0.0)
        self.assertEqual(result["sample_size"], 30)
        self.assertFalse(result["calibration_certified"])
        self.assertFalse(result["pup_allowed"])
        self.assertFalse(result["ex_final_allowed"])


if __name__ == "__main__":
    unittest.main()
