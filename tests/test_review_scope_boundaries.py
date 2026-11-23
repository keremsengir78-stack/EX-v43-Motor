"""Independent evidence boundaries across three non-interchangeable review scopes."""
import unittest

from ex_multileague_queue_validation import validate


def queue():
    return {
        "ex_final_allowed": False, "score_verified": False,
        "total_review_queue": 1506, "exported": 100,
        "truncated": True, "queue_version": 2,
        "fixtures": [{"league": "en.1",
                      "review_status": "REQUIRES_INDEPENDENT_SOURCE_REVIEW"}]
                    * 100,
    }


def diagnostics():
    return {
        "unmatched_total": 1506,
        "by_league": {
            "en.1": {"count": 307}, "es.1": {"count": 442},
            "fr.1": {"count": 329}, "it.1": {"count": 428},
        },
    }


class ReviewScopeSafetyTests(unittest.TestCase):
    def test_scoped_queue_remains_unverified(self):
        result = validate(queue(), diagnostics())
        self.assertEqual(result["total"], 1506)
        self.assertEqual(result["exported"], 100)
        self.assertFalse(result["score_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_legacy_total_cannot_replace_scoped_queue_total(self):
        item = queue()
        item["total_review_queue"] = 1845
        with self.assertRaises(ValueError):
            validate(item, diagnostics())

    def test_strict_reconciliation_total_cannot_replace_review_queue_total(self):
        item = queue()
        item["total_review_queue"] = 1177
        with self.assertRaises(ValueError):
            validate(item, diagnostics())

    def test_unverified_review_cannot_be_promoted_by_a_boolean(self):
        for field in ("score_verified", "ex_final_allowed"):
            item = queue()
            item[field] = True
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(item, diagnostics())

    def test_diagnostic_league_totals_cannot_hide_a_discrepancy(self):
        item = diagnostics()
        item["by_league"]["it.1"]["count"] = 429
        with self.assertRaises(ValueError):
            validate(queue(), item)


if __name__ == "__main__":
    unittest.main()
