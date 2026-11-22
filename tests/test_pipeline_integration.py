"""End-to-end synthetic historical audit tests; never external verification."""
import copy
import unittest

from ex_calibration_audit import audit_predictions
from ex_out_of_sample_audit import audit_out_of_sample
from ex_final_readiness import evaluate_final_readiness

CUTOFF = "2026-03-01T00:00:00Z"
BOUNDARY = "2026-01-01T00:00:00Z"
PIPELINE = {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"}


def synthetic_records():
    rows = []
    for i in range(60):
        training = i < 30
        day = "2025-12-15" if training else "2026-02-15"
        rows.append({
            "fixture_id": "fixture-%02d" % i,
            "market": "KG_VAR",
            "probability": [0.2, 0.3, 0.7, 0.9, 1.0][i % 5],
            "outcome": i % 2,
            "predicted_at": day + "T10:00:00Z",
            "kickoff_at": day + "T12:00:00Z",
            "settled_at": day + "T14:00:00Z",
        })
    return rows


def measured_chain():
    historical = audit_out_of_sample(
        synthetic_records(), "KG_VAR", BOUNDARY, CUTOFF,
        min_train=30, min_test=30)
    measured = audit_predictions(
        historical["split"]["test"], "KG_VAR", CUTOFF, min_samples=30)
    return measured, historical


class PipelineIntegrationTests(unittest.TestCase):
    def test_real_auditors_complete_but_external_gate_stays_closed(self):
        measured, historical = measured_chain()
        self.assertEqual(measured["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertEqual(historical["status"], "OUT_OF_SAMPLE_AUDIT_COMPLETE_NOT_CERTIFIED")
        result = evaluate_final_readiness(PIPELINE, measured, historical)
        self.assertEqual(result["missing_checks"], ["external_evidence"])
        self.assertFalse(result["ex_final_allowed"])
        self.assertFalse(result["externally_verified"])

    def test_tampered_holdout_brier_is_rejected(self):
        measured, historical = measured_chain()
        historical["evaluation"]["brier_score"] = 0.0
        result = evaluate_final_readiness(PIPELINE, measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_tampered_holdout_probability_is_rejected(self):
        measured, historical = measured_chain()
        historical["split"]["test"][0]["probability"] = 0.8
        result = evaluate_final_readiness(PIPELINE, measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_tampered_training_boundary_is_rejected(self):
        measured, historical = measured_chain()
        historical["split"]["train"][0]["settled_at"] = "2026-01-02T14:00:00Z"
        result = evaluate_final_readiness(PIPELINE, measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_cross_market_audits_cannot_be_combined(self):
        measured, historical = measured_chain()
        measured = copy.deepcopy(measured)
        measured["market"] = "MS1"
        result = evaluate_final_readiness(PIPELINE, measured, historical)
        self.assertIn("calibration:historical_market_mismatch", result["issues"])
        self.assertIn("calibration", result["missing_checks"])


if __name__ == "__main__":
    unittest.main()
