import unittest
from ex_temporal_validation import chronological_split


def item(i, train):
    return {"fixture_id": str(i), "market": "KG_VAR",
            "predicted_at": "2025-01-01T00:00:00Z" if train else "2026-02-01T00:00:00Z",
            "kickoff_at": "2025-01-02T00:00:00Z" if train else "2026-02-02T00:00:00Z",
            "settled_at": "2025-01-03T00:00:00Z" if train else "2026-02-03T00:00:00Z"}


class TemporalValidationTests(unittest.TestCase):
    def test_strict_chronological_split(self):
        rows = [item(i, True) for i in range(30)] + [item(i, False) for i in range(30, 60)]
        result = chronological_split(rows, "2026-01-01T00:00:00Z")
        self.assertEqual(result["status"], "CHRONOLOGICAL_SPLIT_READY")
        self.assertEqual(len(result["train"]), 30)
        self.assertEqual(len(result["test"]), 30)
        self.assertFalse(result["ex_final_allowed"])

    def test_overlap_is_blocked(self):
        rows = [item(i, True) for i in range(30)] + [item(i, False) for i in range(30, 60)]
        rows[30]["predicted_at"] = "2025-12-31T00:00:00Z"
        result = chronological_split(rows, "2026-01-01T00:00:00Z")
        self.assertIn("record:30:boundary_overlap", result["issues"])

    def test_duplicate_is_blocked(self):
        rows = [item(i, True) for i in range(30)] + [item(i, False) for i in range(30, 60)]
        rows.append(dict(rows[0]))
        result = chronological_split(rows, "2026-01-01T00:00:00Z")
        self.assertIn("record:60:duplicate_or_missing", result["issues"])

    def test_insufficient_test_period_blocks(self):
        rows = [item(i, True) for i in range(30)] + [item(30, False)]
        result = chronological_split(rows, "2026-01-01T00:00:00Z")
        self.assertIn("test:insufficient", result["issues"])

    def test_unhashable_market_blocks_without_exception(self):
        rows = [item(i, True) for i in range(30)] + [item(i, False) for i in range(30, 60)]
        rows[0]["market"] = []
        result = chronological_split(rows, "2026-01-01T00:00:00Z")
        self.assertIn("record:0:duplicate_or_missing", result["issues"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_invalid_threshold_blocks_without_exception(self):
        rows = [item(i, True) for i in range(30)] + [item(i, False) for i in range(30, 60)]
        result = chronological_split(rows, "2026-01-01T00:00:00Z", min_train="30")
        self.assertIn("sample_threshold:invalid", result["issues"])

    def test_offset_boundary_blocks(self):
        result = chronological_split([], "2026-01-01T03:00:00+03:00")
        self.assertIn("evaluation_start:invalid", result["issues"])

    def test_offset_record_timestamp_blocks(self):
        rows = [item(i, True) for i in range(30)] + [item(i, False) for i in range(30, 60)]
        rows[0]["predicted_at"] = "2025-01-01T03:00:00+03:00"
        result = chronological_split(rows, "2026-01-01T00:00:00Z")
        self.assertIn("record:0:timestamp_invalid_or_leakage", result["issues"])

    def test_missing_market_blocks(self):
        rows = [item(i, True) for i in range(30)] + [item(i, False) for i in range(30, 60)]
        del rows[0]["market"]
        result = chronological_split(rows, "2026-01-01T00:00:00Z")
        self.assertIn("record:0:duplicate_or_missing", result["issues"])

    def test_invalid_utc_boundary_blocks(self):
        result = chronological_split([], "2026-01-01")
        self.assertIn("evaluation_start:invalid", result["issues"])


if __name__ == "__main__":
    unittest.main()
