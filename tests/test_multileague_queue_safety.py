"""Regression tests for fail-closed scoped review queue validation."""
import copy
import unittest

from ex_multileague_queue_validation import validate


def example():
    return (
        {"ex_final_allowed": False, "score_verified": False,
         "total_review_queue": 2, "exported": 1, "truncated": True,
         "queue_version": 2, "fixtures": [
             {"league": "en.1", "review_status": "REQUIRES_INDEPENDENT_SOURCE_REVIEW"}]},
        {"unmatched_total": 2, "by_league": {"en.1": {"count": 2}}},
    )


class ReviewQueueSafetyTests(unittest.TestCase):
    def test_valid_scoped_review_does_not_unlock(self):
        q, d = example()
        result = validate(q, d)
        self.assertEqual(result["total"], 2)
        self.assertFalse(result["score_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_rejects_boolean_or_string_counts(self):
        for value in (True, "2", -1, None, 2.0):
            with self.subTest(value=value):
                q, d = example()
                q["total_review_queue"] = value
                with self.assertRaises(ValueError):
                    validate(q, d)

    def test_rejects_malformed_league_counts(self):
        for value in (True, "2", -1, None, 2.0):
            with self.subTest(value=value):
                q, d = example()
                d["by_league"]["en.1"]["count"] = value
                with self.assertRaises(ValueError):
                    validate(q, d)

    def test_rejects_invalid_exported_and_truncation(self):
        for field, value in (("exported", True), ("exported", 3),
                             ("truncated", 1), ("truncated", False)):
            q, d = example()
            q[field] = value
            with self.assertRaises(ValueError):
                validate(q, d)

    def test_rejects_malformed_fixture_and_diagnostics(self):
        for change in ("fixture", "diagnostics", "league"):
            q, d = example()
            if change == "fixture":
                q["fixtures"] = [None]
            elif change == "diagnostics":
                d["by_league"] = []
            else:
                d["by_league"] = {"en.1": None}
            with self.assertRaises(ValueError):
                validate(q, d)


if __name__ == "__main__":
    unittest.main()
