"""Regression coverage for strict score independent review batches."""
import unittest

from ex_strict_score_review_batch import build_review_batch


def report():
    return {"total": 2, "confirmed": 2, "remaining": 0,
            "verified": [{
                "fixture": {"league": "en.1", "season": "2025-26",
                            "date": "2025-08-16", "home": "A", "away": "B",
                            "independent_score_verified": False},
                "score": [1, 0], "verification": "EXACT_TEAM_DATE_SCORE_MATCH",
                "secondary_provider": "provider",
                "secondary_url": "https://example.org/score.csv",
            } for _ in range(2)]}


class StrictScoreReviewBatchTests(unittest.TestCase):
    def test_batch_exports_pending_without_approval(self):
        result = build_review_batch(report(), limit=1)
        self.assertEqual(result["pending_independent_review"], 2)
        self.assertEqual(result["exported"], 1)
        self.assertTrue(result["truncated"])
        self.assertFalse(result["ex_final_allowed"])
        self.assertFalse(result["independent_score_verified"])

    def test_offset_pagination_is_deterministic(self):
        result = build_review_batch(report(), limit=1, offset=1)
        self.assertEqual(result["fixtures"][0]["index"], 1)
        self.assertFalse(result["truncated"])

    def test_mismatched_scope_counts_fail_closed(self):
        item = report()
        item["total"] = 1177
        with self.assertRaises(ValueError):
            build_review_batch(item)

    def test_boolean_or_negative_score_fails_closed(self):
        for score in ([True, 0], [-1, 2], [1], ["1", 0]):
            with self.subTest(score=score):
                item = report()
                item["verified"][0]["score"] = score
                with self.assertRaises(ValueError):
                    build_review_batch(item)

    def test_verified_flag_cannot_be_imported_as_pending(self):
        item = report()
        item["verified"][0]["fixture"]["independent_score_verified"] = True
        with self.assertRaises(ValueError):
            build_review_batch(item)


if __name__ == "__main__":
    unittest.main()
