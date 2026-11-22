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
        self.assertEqual(result["germany_unmatched"], 1)
        self.assertEqual(result["unmatched_by_league"], {"de.1": 1})

    def test_combines_multiple_seasons_for_germany(self):
        audit = {"ex_final_allowed": False, "secondary_unverified": 3,
                 "secondary_review_queue": [
                     {"season": "2025-26", "league": "de.1", "unmatched": [{"id": 1}]},
                     {"season": "2026-27", "league": "de.1", "unmatched": [{"id": 2}]},
                     {"season": "2026-27", "league": "es.1", "unmatched": [{"id": 3}]}]}
        result = summarize(audit)
        self.assertEqual(result["germany_unmatched"], 2)
        self.assertEqual(result["unmatched_by_league"], {"de.1": 2, "es.1": 1})
        self.assertEqual(result["unmatched_total"], 3)
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

    def test_season_source_counts_must_agree(self):
        audit = {"ex_final_allowed": False, "secondary_unverified": 1,
                 "secondary_review_queue": [
                     {"season": "2026-27", "league": "de.1",
                      "unmatched": [{"home": "A", "away": "B"}]}]}
        good = {**audit, "secondary_unmatched_by_season": {"2026-27/de.1": 1,
                                                            "2025-26/de.1": 0}}
        self.assertEqual(summarize(good)["germany_unmatched"], 1)
        for counts in ({"2026-27/de.1": 2}, {"2026-27/es.1": 1},
                       {"2026-27/de.1": -1}, {"2026-27/de.1": True}):
            with self.subTest(counts=counts):
                with self.assertRaises(ValueError):
                    summarize({**audit, "secondary_unmatched_by_season": counts})

    def test_keeps_alias_candidates_and_source_errors(self):
        candidate = {"secondary": "FC Bayern", "primary": "Bayern Munich"}
        error = {"league": "de.1", "error": "source_unavailable"}
        audit = {"ex_final_allowed": False, "secondary_unverified": 1,
                 "secondary_source_errors": [error],
                 "secondary_review_queue": [
                     {"season": "2026-27", "league": "de.1",
                      "suggestions": [candidate], "unmatched": [{"home": "FC Bayern"}]}]}
        result = summarize(audit)
        self.assertEqual(result["groups"][0]["alias_suggestions"], [candidate])
        self.assertEqual(result["source_errors"], [error])
        self.assertEqual(result["groups_with_alias_suggestions"], 1)
        for key, value in (("secondary_source_errors", "bad"),
                           ("secondary_review_queue", [
                               {"season": "2026-27", "league": "de.1",
                                "suggestions": "bad", "unmatched": [{}]}])):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    summarize({**audit, key: value})

    def test_rejects_missing_queue(self):
        with self.assertRaises(ValueError):
            summarize({"secondary_unverified": 0})
