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
        self.assertEqual(result["missing_checks"], ["calibration", "historical_validation", "external_evidence"])
        self.assertFalse(result["ex_final_allowed"])

    def test_measured_audits_still_cannot_unlock_external_evidence(self):
        measured = {"status": "AUDIT_COMPLETE_NOT_CALIBRATED",
                    "market": "KG_VAR",
                    "sample_size": 100, "brier_score": 0.22,
                    "expected_calibration_error": 0.05,
                    "maximum_calibration_error": 0.05,
                    "mean_predicted": 0.5, "observed_rate": 0.45,
                    "reliability_bins": [{"count": 100,
                                          "mean_predicted": 0.5,
                                          "observed_rate": 0.45}]}
        historical = {"status": "OUT_OF_SAMPLE_AUDIT_COMPLETE_NOT_CERTIFIED",
                      "split": {"status": "CHRONOLOGICAL_SPLIT_READY",
                                "evaluation_start": "2026-01-01T00:00:00Z",
                                "test": [{"fixture_id": str(i), "market": "KG_VAR",
                                          "predicted_at": "2026-01-02T10:00:00Z",
                                          "kickoff_at": "2026-01-02T12:00:00Z",
                                          "settled_at": "2026-01-02T14:00:00Z"}
                                         for i in range(100)]},
                      "evaluation": measured}
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertEqual(result["missing_checks"], ["external_evidence"])
        self.assertFalse(result["ex_final_allowed"])

    def test_incorrect_mean_prediction_is_rejected(self):
        report = {"status": "AUDIT_COMPLETE_NOT_CALIBRATED",
                  "sample_size": 100, "brier_score": 0.22,
                  "expected_calibration_error": 0.05,
                  "maximum_calibration_error": 0.05,
                  "mean_predicted": 0.8, "observed_rate": 0.45,
                  "reliability_bins": [{"count": 100,
                                        "mean_predicted": 0.5,
                                        "observed_rate": 0.45}]}
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"}, report)
        self.assertIn("calibration", result["missing_checks"])

    def test_incorrect_calibration_error_is_rejected(self):
        report = {"status": "AUDIT_COMPLETE_NOT_CALIBRATED",
                  "sample_size": 100, "brier_score": 0.22,
                  "expected_calibration_error": 0.3,
                  "maximum_calibration_error": 0.05,
                  "reliability_bins": [{"count": 100,
                                        "mean_predicted": 0.5,
                                        "observed_rate": 0.45}]}
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"}, report)
        self.assertIn("calibration", result["missing_checks"])

    def test_reliability_bins_must_match_sample_size(self):
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            {"status": "AUDIT_COMPLETE_NOT_CALIBRATED",
             "sample_size": 100, "brier_score": 0.22,
             "expected_calibration_error": 0.08,
             "maximum_calibration_error": 0.16,
             "reliability_bins": [{"count": 99, "mean_predicted": 0.5,
                                   "observed_rate": 0.45}]})
        self.assertIn("calibration", result["missing_checks"])

    def test_holdout_count_mismatch_blocks(self):
        measured = {"status": "AUDIT_COMPLETE_NOT_CALIBRATED",
                    "sample_size": 100, "brier_score": 0.22,
                    "expected_calibration_error": 0.05,
                    "maximum_calibration_error": 0.05,
                    "mean_predicted": 0.5, "observed_rate": 0.45,
                    "reliability_bins": [{"count": 100,
                                          "mean_predicted": 0.5,
                                          "observed_rate": 0.45}]}
        historical = {"status": "OUT_OF_SAMPLE_AUDIT_COMPLETE_NOT_CERTIFIED",
                      "split": {"status": "CHRONOLOGICAL_SPLIT_READY",
                                "test": [{} for _ in range(99)]},
                      "evaluation": measured}
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_holdout_rejects_duplicate_fixtures(self):
        self._assert_bad_holdout("duplicate")

    def test_holdout_rejects_wrong_market(self):
        self._assert_bad_holdout("market")

    def test_holdout_rejects_prediction_before_boundary(self):
        self._assert_bad_holdout("boundary")

    def test_holdout_rejects_temporal_leakage(self):
        self._assert_bad_holdout("time")

    def _assert_bad_holdout(self, defect):
        measured = {"status": "AUDIT_COMPLETE_NOT_CALIBRATED",
                    "market": "KG_VAR", "sample_size": 30, "brier_score": 0.22,
                    "expected_calibration_error": 0.05,
                    "maximum_calibration_error": 0.05,
                    "mean_predicted": 0.5, "observed_rate": 0.45,
                    "reliability_bins": [{"count": 30,
                                          "mean_predicted": 0.5,
                                          "observed_rate": 0.45}]}
        rows = [{"fixture_id": str(i), "market": "KG_VAR",
                 "predicted_at": "2026-01-02T10:00:00Z",
                 "kickoff_at": "2026-01-02T12:00:00Z",
                 "settled_at": "2026-01-02T14:00:00Z"} for i in range(30)]
        if defect == "duplicate":
            rows[1]["fixture_id"] = rows[0]["fixture_id"]
        elif defect == "market":
            rows[1]["market"] = "MS1"
        elif defect == "boundary":
            rows[1]["predicted_at"] = "2025-12-31T10:00:00Z"
            rows[1]["kickoff_at"] = "2025-12-31T12:00:00Z"
            rows[1]["settled_at"] = "2025-12-31T14:00:00Z"
        else:
            rows[1]["settled_at"] = "2026-01-02T11:00:00Z"
        historical = {"status": "OUT_OF_SAMPLE_AUDIT_COMPLETE_NOT_CERTIFIED",
                      "split": {"status": "CHRONOLOGICAL_SPLIT_READY",
                                "evaluation_start": "2026-01-01T00:00:00Z",
                                "test": rows}, "evaluation": measured}
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_fabricated_nan_metric_is_rejected(self):
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            {"status": "AUDIT_COMPLETE_NOT_CALIBRATED",
             "sample_size": 100, "brier_score": float("nan"),
             "expected_calibration_error": 0.1, "maximum_calibration_error": 0.2})
        self.assertIn("calibration", result["missing_checks"])

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
