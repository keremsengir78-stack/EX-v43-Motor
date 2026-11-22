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
        measured, historical = self._valid_holdout()
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertEqual(result["missing_checks"], ["external_evidence"])
        self.assertFalse(result["ex_final_allowed"])

    @staticmethod
    def _valid_holdout():
        rows = [{"fixture_id": str(i), "market": "KG_VAR",
                 "probability": 0.5, "outcome": i % 2,
                 "predicted_at": "2026-01-02T10:00:00Z",
                 "kickoff_at": "2026-01-02T12:00:00Z",
                 "settled_at": "2026-01-02T14:00:00Z"} for i in range(30)]
        measured = {"status": "AUDIT_COMPLETE_NOT_CALIBRATED",
                    "market": "KG_VAR", "sample_size": 30,
                    "brier_score": 0.25, "expected_calibration_error": 0.0,
                    "maximum_calibration_error": 0.0,
                    "mean_predicted": 0.5, "observed_rate": 0.5,
                    "reliability_bins": [{"range": "50-60", "count": 30,
                                          "mean_predicted": 0.5,
                                          "observed_rate": 0.5}]}
        historical = {"status": "OUT_OF_SAMPLE_AUDIT_COMPLETE_NOT_CERTIFIED",
                      "split": {"status": "CHRONOLOGICAL_SPLIT_READY",
                                "evaluation_start": "2026-01-01T00:00:00Z",
                                "train": [{"fixture_id": "train-" + str(i),
                                           "market": "KG_VAR",
                                           "probability": 0.5, "outcome": i % 2,
                                           "predicted_at": "2025-12-30T10:00:00Z",
                                           "kickoff_at": "2025-12-30T12:00:00Z",
                                           "settled_at": "2025-12-30T14:00:00Z"}
                                          for i in range(30)],
                                "test": rows},
                      "evaluation": measured}
        return measured, historical

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
        measured, historical = self._valid_holdout()
        rows = historical["split"]["test"]
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
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_invalid_probability_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["test"][0]["probability"] = float("nan")
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_invalid_outcome_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["test"][0]["outcome"] = True
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_non_utc_timestamp_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["test"][0]["predicted_at"] = "2026-01-02T12:00:00+02:00"
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_training_test_overlap_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["train"] = [{
            "fixture_id": "0", "market": "KG_VAR",
            "settled_at": "2025-12-31T10:00:00Z"}]
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_fabricated_brier_score_blocks(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"] = dict(measured, brier_score=0.1)
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_training_insufficient_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["train"] = historical["split"]["train"][:29]
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_training_time_leakage_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["train"][0]["settled_at"] = "2026-01-02T14:00:00Z"
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_training_invalid_prediction_order_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["train"][0]["predicted_at"] = "2025-12-30T13:00:00Z"
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_training_duplicate_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["train"][1]["fixture_id"] = "train-0"
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_cross_audit_market_mismatch_blocks(self):
        measured, historical = self._valid_holdout()
        other = dict(measured, market="MS1")
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            other, historical)
        self.assertIn("calibration:historical_market_mismatch", result["issues"])
        self.assertIn("calibration", result["missing_checks"])

    def test_training_invalid_probability_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["train"][0]["probability"] = 1.5
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_training_invalid_outcome_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["train"][0]["outcome"] = "1"
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_unsupported_calibration_market_blocks(self):
        measured, historical = self._valid_holdout()
        measured["market"] = "UNKNOWN"
        self.assertIn("calibration", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_wrong_calibration_bin_range_blocks(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"] = dict(measured)
        historical["evaluation"]["reliability_bins"] = [
            dict(measured["reliability_bins"][0], range="60-70")]
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_wrong_calibration_bin_observed_rate_blocks(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"] = dict(measured)
        historical["evaluation"]["reliability_bins"] = [
            dict(measured["reliability_bins"][0], observed_rate=0.4)]
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_duplicate_bin_range_blocks(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"]["reliability_bins"].append(
            dict(historical["evaluation"]["reliability_bins"][0]))
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_missing_nonempty_bin_blocks(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"]["reliability_bins"] = []
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_invented_bin_range_blocks(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"]["reliability_bins"][0]["range"] = "55-65"
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_extra_empty_bin_blocks(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"]["reliability_bins"].append(
            {"range": "00-10", "count": 0, "mean_predicted": 0.0,
             "observed_rate": 0.0})
        self.assertIn("historical_validation", evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)["missing_checks"])

    def test_probability_one_uses_final_bin(self):
        measured, historical = self._valid_holdout()
        for row in historical["split"]["test"]:
            row["probability"] = 1.0
            row["outcome"] = 1
        measured.update(brier_score=0.0, expected_calibration_error=0.0,
                        maximum_calibration_error=0.0, mean_predicted=1.0,
                        observed_rate=1.0,
                        reliability_bins=[{"range": "90-100", "count": 30,
                                           "mean_predicted": 1.0,
                                           "observed_rate": 1.0}])
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertEqual(result["missing_checks"], ["external_evidence"])

    def test_unhashable_bin_label_blocks_without_exception(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"]["reliability_bins"][0]["range"] = []
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_null_bin_label_blocks(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"]["reliability_bins"][0]["range"] = None
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_probability_zero_uses_first_bin(self):
        measured, historical = self._valid_holdout()
        for row in historical["split"]["test"]:
            row["probability"] = 0.0
            row["outcome"] = 0
        measured.update(brier_score=0.0, expected_calibration_error=0.0,
                        maximum_calibration_error=0.0, mean_predicted=0.0,
                        observed_rate=0.0,
                        reliability_bins=[{"range": "00-10", "count": 30,
                                           "mean_predicted": 0.0,
                                           "observed_rate": 0.0}])
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertEqual(result["missing_checks"], ["external_evidence"])

    def test_exact_tenth_boundary_uses_upper_bin(self):
        measured, historical = self._valid_holdout()
        for row in historical["split"]["test"]:
            row["probability"] = 0.3
            row["outcome"] = 0
        measured.update(brier_score=0.09, expected_calibration_error=0.3,
                        maximum_calibration_error=0.3, mean_predicted=0.3,
                        observed_rate=0.0,
                        reliability_bins=[{"range": "30-40", "count": 30,
                                           "mean_predicted": 0.3,
                                           "observed_rate": 0.0}])
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertEqual(result["missing_checks"], ["external_evidence"])

    def test_just_below_tenth_boundary_uses_lower_bin(self):
        measured, historical = self._valid_holdout()
        for row in historical["split"]["test"]:
            row["probability"] = 0.299
            row["outcome"] = 0
        measured.update(brier_score=0.089401, expected_calibration_error=0.299,
                        maximum_calibration_error=0.299, mean_predicted=0.299,
                        observed_rate=0.0,
                        reliability_bins=[{"range": "20-30", "count": 30,
                                           "mean_predicted": 0.299,
                                           "observed_rate": 0.0}])
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertEqual(result["missing_checks"], ["external_evidence"])

    def test_unhashable_market_blocks_without_exception(self):
        measured, historical = self._valid_holdout()
        measured["market"] = []
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("calibration", result["missing_checks"])

    def test_non_numeric_ece_blocks_without_exception(self):
        measured, historical = self._valid_holdout()
        measured["expected_calibration_error"] = "bad"
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("calibration", result["missing_checks"])

    def test_non_numeric_mean_blocks_without_exception(self):
        measured, historical = self._valid_holdout()
        measured["mean_predicted"] = []
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("calibration", result["missing_checks"])

    def test_unhashable_historical_market_blocks(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"]["market"] = {}
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_invalid_bin_count_blocks(self):
        measured, historical = self._valid_holdout()
        historical["evaluation"]["reliability_bins"][0]["count"] = True
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_calibration_report_with_issues_blocks(self):
        measured, historical = self._valid_holdout()
        measured["issues"] = ["sample:insufficient"]
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("calibration", result["missing_checks"])

    def test_calibration_claiming_certification_blocks(self):
        measured, historical = self._valid_holdout()
        measured["calibration_certified"] = True
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("calibration", result["missing_checks"])

    def test_historical_report_with_issues_blocks(self):
        measured, historical = self._valid_holdout()
        historical["issues"] = ["split:boundary_overlap"]
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_historical_claiming_certification_blocks(self):
        measured, historical = self._valid_holdout()
        historical["calibration_certified"] = True
        result = evaluate_final_readiness(
            {"status": "RECONCILED_WITH_METADATA_UNVERIFIED"},
            measured, historical)
        self.assertIn("historical_validation", result["missing_checks"])

    def test_split_report_with_issues_blocks(self):
        measured, historical = self._valid_holdout()
        historical["split"]["issues"] = ["record:0:boundary_overlap"]
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
