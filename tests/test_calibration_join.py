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
