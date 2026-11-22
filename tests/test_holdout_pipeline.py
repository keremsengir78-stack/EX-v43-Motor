import unittest
from ex_holdout_pipeline import audit_joined_holdout


def data():
    fixtures, predictions = [], []
    for i in range(60):
        train = i < 30
        kickoff = ("2025-06-01T12:00:00Z" if train else "2026-06-01T12:00:00Z")
        predicted = ("2025-05-01T12:00:00Z" if train else "2026-05-01T12:00:00Z")
        settled = ("2025-06-02T12:00:00Z" if train else "2026-06-02T12:00:00Z")
        fid = "match-%02d" % i
        fixtures.append({"fixture_id": fid, "kickoff_at": kickoff,
                         "home_goals": 2, "away_goals": 1, "verified": True,
                         "source": "independent-fixture-record",
                         "status": "finished", "settled_at": settled})
        predictions.append({"fixture_id": fid, "market": "KG_VAR",
                            "probability": 0.6, "predicted_at": predicted,
                            "kickoff_at": kickoff, "settled_at": settled,
                            "verified": True, "source": "frozen-prediction"})
    return predictions, fixtures


class HoldoutPipelineTests(unittest.TestCase):
    def run_audit(self, predictions=None, fixtures=None, **kwargs):
        p, f = data()
        return audit_joined_holdout(p if predictions is None else predictions,
                                    f if fixtures is None else fixtures,
                                    kwargs.pop("market", "KG_VAR"),
                                    kwargs.pop("evaluation_start", "2026-01-01T00:00:00Z"),
                                    kwargs.pop("cutoff", "2026-07-01T00:00:00Z"),
                                    **kwargs)

    def test_identical_prediction_and_result_source_blocks(self):
        p, f = data()
        p[0]["source"] = "independent-fixture-record"
        result = self.run_audit(predictions=p, fixtures=f)
        self.assertEqual(result["issues"], ["sources:prediction_result_overlap"])
        self.assertIsNone(result["join"])

    def test_overlap_in_later_prediction_blocks(self):
        p, f = data()
        p[-1]["source"] = "independent-fixture-record"
        result = self.run_audit(predictions=p, fixtures=f)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ex_final_allowed"])

    def test_overlap_in_later_fixture_blocks(self):
        p, f = data()
        f[-1]["source"] = "frozen-prediction"
        result = self.run_audit(predictions=p, fixtures=f)
        self.assertIn("sources:prediction_result_overlap", result["issues"])

    def test_distinct_source_labels_still_not_certified(self):
        result = self.run_audit()
        self.assertEqual(result["status"], "HOLDOUT_AUDITED_NOT_CERTIFIED")
        self.assertFalse(result["calibration_certified"])

    def test_holdout_missing_fixture_settlement_provenance_blocks(self):
        p, f = data()
        del f[0]["settled_at"]
        result = self.run_audit(predictions=p, fixtures=f)
        self.assertEqual(result["issues"], ["fixtures:settlement_provenance_missing"])
        self.assertIsNone(result["join"])

    def test_holdout_blank_fixture_settlement_provenance_blocks(self):
        p, f = data()
        f[0]["settled_at"] = " "
        result = self.run_audit(predictions=p, fixtures=f)
        self.assertEqual(result["issues"], ["fixtures:settlement_provenance_missing"])

    def test_holdout_missing_prediction_source_blocks(self):
        p, f = data()
        del p[0]["source"]
        result = self.run_audit(predictions=p, fixtures=f)
        self.assertEqual(result["issues"], ["predictions:source_missing"])

    def test_holdout_empty_prediction_source_blocks(self):
        p, f = data()
        p[0]["source"] = ""
        result = self.run_audit(predictions=p, fixtures=f)
        self.assertEqual(result["issues"], ["predictions:source_missing"])

    def test_holdout_provenance_present_remains_not_certified(self):
        result = self.run_audit()
        self.assertEqual(result["status"], "HOLDOUT_AUDITED_NOT_CERTIFIED")
        self.assertFalse(result["pup_allowed"])
        self.assertFalse(result["ex_final_allowed"])

    def test_evaluation_start_equal_cutoff_blocks(self):
        result = self.run_audit(evaluation_start="2026-07-01T00:00:00Z")
        self.assertEqual(result["issues"], ["evaluation_window:invalid"])

    def test_evaluation_start_after_cutoff_blocks(self):
        result = self.run_audit(evaluation_start="2026-08-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["join"])

    def test_non_utc_evaluation_start_blocks_early(self):
        result = self.run_audit(evaluation_start="2026-01-01T03:00:00+03:00Z")
        self.assertEqual(result["issues"], ["evaluation_window:invalid"])

    def test_invalid_cutoff_blocks_early(self):
        result = self.run_audit(cutoff="invalid")
        self.assertEqual(result["issues"], ["evaluation_window:invalid"])

    def test_boundary_overlap_blocks_without_holdout(self):
        p, f = data()
        p[0]["predicted_at"] = "2025-12-31T12:00:00Z"
        f[0]["kickoff_at"] = "2026-01-01T12:00:00Z"
        f[0]["settled_at"] = "2026-01-02T12:00:00Z"
        p[0]["kickoff_at"] = f[0]["kickoff_at"]
        p[0]["settled_at"] = f[0]["settled_at"]
        result = self.run_audit(predictions=p, fixtures=f)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("boundary_overlap" in x for x in result["issues"]))

    def test_complete_chronological_audit_never_certifies(self):
        result = self.run_audit()
        self.assertEqual(result["status"], "HOLDOUT_AUDITED_NOT_CERTIFIED")
        self.assertFalse(result["ex_final_allowed"])
        self.assertFalse(result["calibration_certified"])

    def test_missing_fixture_blocks(self):
        p, f = data()
        result = self.run_audit(predictions=p[:-1], fixtures=f)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("fixture_coverage" in x for x in result["issues"]))

    def test_wrong_market_blocks(self):
        result = self.run_audit(market="WRONG")
        self.assertEqual(result["issues"], ["market:unsupported"])

    def test_insufficient_holdout_blocks(self):
        result = self.run_audit(min_test=31)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ex_final_allowed"])

    def test_bad_settlement_blocks(self):
        p, f = data()
        f[0]["settled_at"] = "2027-01-01T00:00:00Z"
        result = self.run_audit(predictions=p, fixtures=f)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("settlement" in x for x in result["issues"]))


if __name__ == "__main__":
    unittest.main()
