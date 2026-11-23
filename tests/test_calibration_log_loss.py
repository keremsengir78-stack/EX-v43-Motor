"""Regression checks for leakage-safe calibration log-loss diagnostics."""
import math
import unittest
from ex_calibration_audit import audit_predictions


def sample(i, probability, outcome):
    return {"fixture_id": "fixture-%d" % i, "market": "KG_VAR",
            "probability": probability, "outcome": outcome,
            "predicted_at": "2026-01-01T08:00:00Z",
            "kickoff_at": "2026-01-01T12:00:00Z",
            "settled_at": "2026-01-01T15:00:00Z"}


class LogLossAuditTests(unittest.TestCase):
    def test_log_loss_and_brier_for_balanced_predictions(self):
        rows = [sample(i, 0.5, i % 2) for i in range(30)]
        result = audit_predictions(rows, "KG_VAR", "2026-02-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertAlmostEqual(result["log_loss"], math.log(2), places=7)
        self.assertAlmostEqual(result["brier_score"], 0.25)
        self.assertFalse(result["ex_final_allowed"])

    def test_extreme_probabilities_have_finite_log_loss(self):
        rows = [sample(i, 0.0 if i % 2 else 1.0, i % 2) for i in range(30)]
        result = audit_predictions(rows, "KG_VAR", "2026-02-01T00:00:00Z", min_samples=30)
        self.assertTrue(math.isfinite(result["log_loss"]))
        self.assertGreater(result["log_loss"], 30)

    def test_temporal_leakage_suppresses_all_metrics(self):
        rows = [sample(i, 0.6, i % 2) for i in range(30)]
        rows[0]["predicted_at"] = "2026-01-01T13:00:00Z"
        result = audit_predictions(rows, "KG_VAR", "2026-02-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["log_loss"])
        self.assertIsNone(result["brier_score"])

    def test_small_sample_does_not_publish_metric(self):
        result = audit_predictions([sample(1, 0.7, 1)], "KG_VAR",
                                   "2026-02-01T00:00:00Z", min_samples=30)
        self.assertIn("sample:insufficient", result["issues"])
        self.assertIsNone(result["log_loss"])


if __name__ == "__main__":
    unittest.main()
