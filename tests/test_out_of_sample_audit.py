import unittest
from ex_out_of_sample_audit import audit_out_of_sample


def row(i, train):
    return {"fixture_id": str(i), "market": "KG_VAR", "probability": 0.7,
            "outcome": 1,
            "predicted_at": "2025-01-01T00:00:00Z" if train else "2026-02-01T00:00:00Z",
            "kickoff_at": "2025-01-02T00:00:00Z" if train else "2026-02-02T00:00:00Z",
            "settled_at": "2025-01-03T00:00:00Z" if train else "2026-02-03T00:00:00Z"}


def dataset():
    return [row(i, True) for i in range(30)] + [row(i, False) for i in range(30, 60)]


class OutOfSampleAuditTests(unittest.TestCase):
    def test_only_holdout_is_scored(self):
        result = audit_out_of_sample(dataset(), "KG_VAR", "2026-01-01T00:00:00Z",
                                     "2026-03-01T00:00:00Z")
        self.assertEqual(result["status"], "OUT_OF_SAMPLE_AUDIT_COMPLETE_NOT_CERTIFIED")
        self.assertEqual(result["evaluation"]["sample_size"], 30)
        self.assertEqual(result["evaluation"]["brier_score"], 0.09)
        self.assertFalse(result["calibration_certified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_unhashable_market_blocks(self):
        result = audit_out_of_sample(dataset(), [], "2026-01-01T00:00:00Z",
                                     "2026-03-01T00:00:00Z")
        self.assertIn("market:unsupported", result["issues"])

    def test_non_numeric_test_threshold_blocks(self):
        result = audit_out_of_sample(dataset(), "KG_VAR", "2026-01-01T00:00:00Z",
                                     "2026-03-01T00:00:00Z", min_test="30")
        self.assertIn("sample_threshold:invalid", result["issues"])

    def test_boolean_train_threshold_blocks(self):
        result = audit_out_of_sample(dataset(), "KG_VAR", "2026-01-01T00:00:00Z",
                                     "2026-03-01T00:00:00Z", min_train=True)
        self.assertIn("sample_threshold:invalid", result["issues"])

    def test_train_threshold_below_thirty_blocks(self):
        result = audit_out_of_sample(dataset(), "KG_VAR", "2026-01-01T00:00:00Z",
                                     "2026-03-01T00:00:00Z", min_train=29)
        self.assertIn("sample_threshold:invalid", result["issues"])

    def test_test_threshold_below_thirty_blocks(self):
        result = audit_out_of_sample(dataset(), "KG_VAR", "2026-01-01T00:00:00Z",
                                     "2026-03-01T00:00:00Z", min_test=29)
        self.assertIn("sample_threshold:invalid", result["issues"])

    def test_boundary_overlap_blocks(self):
        rows = dataset()
        rows[30]["predicted_at"] = "2025-12-31T00:00:00Z"
        result = audit_out_of_sample(rows, "KG_VAR", "2026-01-01T00:00:00Z",
                                     "2026-03-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["evaluation"])

    def test_market_mismatch_blocks(self):
        rows = dataset()
        rows[0]["market"] = "MS1"
        result = audit_out_of_sample(rows, "KG_VAR", "2026-01-01T00:00:00Z",
                                     "2026-03-01T00:00:00Z")
        self.assertIn("record:0:market_mismatch", result["issues"])

    def test_insufficient_holdout_blocks(self):
        rows = dataset()[:31]
        result = audit_out_of_sample(rows, "KG_VAR", "2026-01-01T00:00:00Z",
                                     "2026-03-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("test:insufficient" in x for x in result["issues"]))


if __name__ == "__main__":
    unittest.main()
