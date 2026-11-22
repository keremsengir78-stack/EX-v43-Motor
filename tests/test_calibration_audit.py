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

    def test_reliability_bins_and_observed_frequency(self):
        records = [row(i, 0.75, 1 if i % 2 == 0 else 0) for i in range(100)]
        result = audit_predictions(records, "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual(result["mean_predicted"], 0.75)
        self.assertEqual(result["observed_rate"], 0.5)
        self.assertEqual(result["reliability_bins"], [{
            "range": "70-80", "count": 100, "mean_predicted": 0.75, "observed_rate": 0.5
        }])
        self.assertFalse(result["calibration_certified"])

    def test_calibration_errors_capture_overconfidence(self):
        records = [row(i, 0.75, 1 if i % 2 == 0 else 0) for i in range(100)]
        result = audit_predictions(records, "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual(result["expected_calibration_error"], 0.25)
        self.assertEqual(result["maximum_calibration_error"], 0.25)
        self.assertFalse(result["calibration_certified"])

    def test_calibration_errors_weight_bins_by_sample_count(self):
        records = [row(i, 0.2, 0) for i in range(80)]
        records += [row(i, 0.9, 0) for i in range(80, 100)]
        result = audit_predictions(records, "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual(result["expected_calibration_error"], 0.34)
        self.assertEqual(result["maximum_calibration_error"], 0.9)

    def test_probability_one_is_in_final_bin(self):
        records = [row(i, 1.0, 1) for i in range(100)]
        result = audit_predictions(records, "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual(result["reliability_bins"][0]["range"], "90-100")
        self.assertEqual(result["reliability_bins"][0]["count"], 100)
        self.assertEqual(result["brier_score"], 0.0)
        self.assertFalse(result["ex_final_allowed"])

    def test_blocked_audit_never_emits_reliability_metrics(self):
        result = audit_predictions([row(1)], "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual(result["reliability_bins"], [])
        self.assertIsNone(result["mean_predicted"])
        self.assertIsNone(result["observed_rate"])
        self.assertIsNone(result["expected_calibration_error"])
        self.assertIsNone(result["maximum_calibration_error"])

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

    def test_unhashable_market_fails_closed(self):
        result = audit_predictions([row(1)], [], "2026-02-01T00:00:00Z")
        self.assertIn("market:unsupported", result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_invalid_min_samples_fails_closed(self):
        result = audit_predictions([row(1)], "KG_VAR",
                                   "2026-02-01T00:00:00Z", min_samples="100")
        self.assertIn("min_samples:invalid", result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_non_utc_cutoff_is_rejected(self):
        result = audit_predictions([row(1)], "KG_VAR",
                                   "2026-02-01T03:00:00+03:00")
        self.assertIn("cutoff:invalid", result["issues"])

    def test_offset_prediction_is_rejected(self):
        record = row(1)
        record["predicted_at"] = "2026-01-01T13:00:00+03:00"
        result = audit_predictions([record], "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertIn("record:0:invalid_timestamp", result["issues"])

    def test_naive_settlement_is_rejected(self):
        record = row(1)
        record["settled_at"] = "2026-01-01T15:00:00"
        result = audit_predictions([record], "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertIn("record:0:invalid_timestamp", result["issues"])

    def test_exact_decimal_boundary_uses_upper_bin(self):
        records = [row(i, 0.3, 0) for i in range(100)]
        result = audit_predictions(records, "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual(result["reliability_bins"][0]["range"], "30-40")

    def test_just_below_boundary_uses_lower_bin(self):
        records = [row(i, 0.299, 0) for i in range(100)]
        result = audit_predictions(records, "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual(result["reliability_bins"][0]["range"], "20-30")

    def test_mixed_boundary_bins_cover_all_records(self):
        records = [row(i, 0.3 if i % 2 else 0.299, 0)
                   for i in range(100)]
        result = audit_predictions(records, "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual([b["range"] for b in result["reliability_bins"]],
                         ["20-30", "30-40"])
        self.assertEqual(sum(b["count"] for b in result["reliability_bins"]), 100)

    def test_zero_probability_uses_first_bin(self):
        result = audit_predictions([row(i, 0.0, 0) for i in range(100)],
                                   "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual(result["reliability_bins"][0]["range"], "00-10")

    def test_all_tenth_boundaries_cover_every_record(self):
        records = [row(i, (i % 11) / 10, 0) for i in range(110)]
        result = audit_predictions(records, "KG_VAR", "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertEqual(sum(b["count"] for b in result["reliability_bins"]), 110)

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
