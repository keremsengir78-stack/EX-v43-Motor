import unittest
from ex_cross_verify import verify
from ex_secondary_review_summary import summarize


class FullEvidenceTests(unittest.TestCase):
    def test_more_than_250_unmatched_records_are_not_truncated(self):
        primary = [
            {"date": "2026-11-01", "league": "de.1",
             "home": f"Home {i}", "away": f"Away {i}",
             "home_goals": 1, "away_goals": 0}
            for i in range(305)
        ]
        comparison = verify(primary, [], "2026-11-22")
        self.assertEqual(comparison["unmatched"], 305)
        self.assertEqual(len(comparison["unmatched_details"]), 305)
        audit = {"ex_final_allowed": False, "secondary_unverified": 305,
                 "secondary_unmatched_by_season": {"2026-27/de.1": 305},
                 "secondary_review_queue": [
                     {"season": "2026-27", "league": "de.1",
                      "unmatched": comparison["unmatched_details"],
                      "suggestions": comparison["alias_suggestions"]}]}
        summary = summarize(audit)
        self.assertEqual(summary["germany_unmatched"], 305)
        self.assertEqual(len(summary["groups"][0]["unmatched_details"]), 305)
        self.assertIs(summary["ex_final_allowed"], False)


if __name__ == "__main__":
    unittest.main()
