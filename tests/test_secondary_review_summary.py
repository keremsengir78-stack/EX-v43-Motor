import unittest
from ex_secondary_review_summary import summarize


class SecondaryReviewSummaryTests(unittest.TestCase):
    def test_preserves_unmatched_evidence_and_blocks_final(self):
        item = {"date": "2026-11-08", "home": "Team A", "away": "Team B",
                "reason": "not_found"}
        audit = {"as_of": "2026-11-22", "ex_final_allowed": False, "secondary_unverified": 1,
                 "secondary_review_queue": [
                     {"season": "2026-27", "league": "de.1", "unmatched": [item]}]}
        result = summarize(audit)
        self.assertEqual(result["unmatched_total"], 1)
        self.assertEqual(result["groups"][0]["unmatched_details"], [item])
        self.assertFalse(result["ex_final_allowed"])

    def test_rejects_missing_or_inconsistent_counts(self):
        base = {"ex_final_allowed": False, "secondary_review_queue": [
            {"season": "2026-27", "league": "de.1",
             "unmatched": [{"home": "A", "away": "B"}]}]}
        for count in (None, 0, 2, True):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    summarize({**base, "secondary_unverified": count})

    def test_rejects_audit_without_explicit_final_lock(self):
        audit = {"secondary_unverified": 0, "secondary_review_queue": []}
        for flag in (None, True, 0):
            with self.subTest(flag=flag):
                with self.assertRaises(ValueError):
                    summarize({**audit, "ex_final_allowed": flag})

    def test_rejects_missing_queue(self):
        with self.assertRaises(ValueError):
            summarize({"secondary_unverified": 0})
