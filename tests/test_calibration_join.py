import unittest
from ex_calibration_join import join_calibration_records


def inputs(n=30):
    fixtures = []
    predictions = []
    for i in range(n):
        fid = str(i)
        kickoff = "2026-01-%02dT12:00:00Z" % (i % 28 + 1)
        fixtures.append({"fixture_id": fid, "kickoff_at": kickoff, "home_goals": 2,
                         "away_goals": 1, "verified": True, "source": "results",
                         "status": "finished"})
        predictions.append({"fixture_id": fid, "market": "KG_VAR", "probability": 0.6,
                            "predicted_at": "2025-12-01T12:00:00Z",
                            "kickoff_at": kickoff, "settled_at": "2026-02-01T12:00:00Z",
                            "verified": True, "source": "frozen-forecast"})
    return predictions, fixtures


class CalibrationJoinTests(unittest.TestCase):
    def test_identical_prediction_result_source_blocks(self):
        predictions, fixtures = inputs()
        predictions[0]["source"] = "results"
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["issues"], ["sources:prediction_result_overlap"])
        self.assertEqual(result["joined_records"], [])

    def test_casefold_source_overlap_blocks(self):
        predictions, fixtures = inputs()
        predictions[-1]["source"] = "RESULTS"
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["audit"])

    def test_whitespace_source_overlap_blocks(self):
        predictions, fixtures = inputs()
        fixtures[0]["source"] = "  FROZEN-FORECAST "
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("sources:prediction_result_overlap", result["issues"])

    def test_unicode_casefold_source_overlap_blocks(self):
        predictions, fixtures = inputs()
        predictions[0]["source"] = "Straße"
        fixtures[0]["source"] = "STRASSE"
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("sources:prediction_result_overlap", result["issues"])

    def test_distinct_source_labels_not_certified(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertFalse(result["calibration_certified"])

    def test_none_fixtures_blocks_without_exception(self):
        predictions, _ = inputs()
        result = join_calibration_records(predictions, None, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ex_final_allowed"])

    def test_numeric_fixtures_blocks_without_exception(self):
        predictions, _ = inputs()
        result = join_calibration_records(predictions, 42, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["joined_records"], [])

    def test_string_fixtures_blocks_without_exception(self):
        predictions, _ = inputs()
        result = join_calibration_records(predictions, "bad", "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["audit"])

    def test_dict_fixtures_blocks_without_exception(self):
        predictions, _ = inputs()
        result = join_calibration_records(predictions, {"fixture_id": "0"}, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["calibration_certified"])

    def test_valid_fixture_list_still_audits(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")

    def test_fixture_settlement_disagreement_blocks(self):
        predictions, fixtures = inputs()
        fixtures[0]["settled_at"] = "2026-02-02T12:00:00Z"
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("prediction:0:settlement_mismatch", result["issues"])

    def test_matching_fixture_settlement_is_accepted(self):
        predictions, fixtures = inputs()
        for fixture in fixtures:
            fixture["settled_at"] = "2026-02-01T12:00:00Z"
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")

    def test_settlement_mismatch_does_not_emit_partial_records(self):
        predictions, fixtures = inputs()
        fixtures[-1]["settled_at"] = "2026-02-02T12:00:00Z"
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["joined_records"], [])
        self.assertIsNone(result["audit"])

    def test_fixture_settlement_utc_offset_disagreement_blocks(self):
        predictions, fixtures = inputs()
        fixtures[0]["settled_at"] = "2026-02-01T15:00:00+03:00Z"
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("outcome:fixture:0:settlement_invalid_or_future", result["issues"])

    def test_fixture_settlement_is_optional_for_legacy_records(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertFalse(result["calibration_certified"])

    def test_boolean_min_samples_blocks_before_audit(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=True)
        self.assertEqual(result["issues"], ["min_samples:invalid"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_below_minimum_sample_threshold_blocks(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=29)
        self.assertIn("min_samples:invalid", result["issues"])

    def test_string_minimum_sample_threshold_blocks(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples="30")
        self.assertIn("min_samples:invalid", result["issues"])

    def test_insufficient_valid_sample_blocks_without_certification(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=31)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("sample:insufficient", result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_unhashable_market_blocks(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions, fixtures, [], "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("market:unsupported", result["issues"])

    def test_prediction_offset_disguised_as_utc_blocks(self):
        predictions, fixtures = inputs()
        predictions[0]["predicted_at"] = "2025-12-01T15:00:00+03:00Z"
        result = join_calibration_records(predictions, fixtures, "KG_VAR", "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("prediction:0:temporal_leakage", result["issues"])

    def test_settlement_offset_disguised_as_utc_blocks(self):
        predictions, fixtures = inputs()
        predictions[0]["settled_at"] = "2026-02-01T15:00:00+03:00Z"
        result = join_calibration_records(predictions, fixtures, "KG_VAR", "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("prediction:0:settlement_invalid", result["issues"])

    def test_different_fixture_ids_same_count_block(self):
        predictions, fixtures = inputs()
        predictions[0]["fixture_id"] = "not-in-fixtures"
        result = join_calibration_records(predictions, fixtures, "KG_VAR", "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("predictions:fixture_coverage_incomplete", result["issues"])

    def test_valid_utc_join_remains_not_certified(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions, fixtures, "KG_VAR", "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertFalse(result["calibration_certified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_complete_join_audits_without_certification(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertEqual(result["audit"]["brier_score"], 0.16)
        self.assertEqual(len(result["joined_records"]), 30)
        self.assertFalse(result["ex_final_allowed"])

    def test_missing_prediction_blocks(self):
        predictions, fixtures = inputs()
        result = join_calibration_records(predictions[:-1], fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("predictions:fixture_coverage_incomplete", result["issues"])

    def test_prediction_after_kickoff_blocks(self):
        predictions, fixtures = inputs()
        predictions[0]["predicted_at"] = "2026-02-10T12:00:00Z"
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("prediction:0:temporal_leakage", result["issues"])

    def test_wrong_kickoff_blocks(self):
        predictions, fixtures = inputs()
        predictions[0]["kickoff_at"] = "2026-01-31T12:00:00Z"
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertIn("prediction:0:kickoff_mismatch", result["issues"])

    def test_duplicate_prediction_blocks(self):
        predictions, fixtures = inputs()
        predictions.append(dict(predictions[0]))
        result = join_calibration_records(predictions, fixtures, "KG_VAR",
                                          "2026-03-01T00:00:00Z", min_samples=30)
        self.assertTrue(any("duplicate" in x for x in result["issues"]))


if __name__ == "__main__":
    unittest.main()
