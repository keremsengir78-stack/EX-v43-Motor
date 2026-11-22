import unittest

from ex_cross_verify import secondary_presence_diagnostic, verify


class SecondaryPresenceTests(unittest.TestCase):
    def setUp(self):
        self.primary = {"date": "2026-11-07", "league": "de.1",
                        "home": "Borussia Dortmund", "away": "SV Elversberg",
                        "home_goals": 2, "away_goals": 0}
        self.other = {"date": "2026-11-07", "league": "de.1",
                      "home": "Borussia Dortmund", "away": "Werder Bremen",
                      "home_goals": 1, "away_goals": 1}

    def test_secondary_day_empty(self):
        result = secondary_presence_diagnostic(self.primary, [], "2026-11-22")
        self.assertEqual(result["source_presence_status"], "SECONDARY_DATE_EMPTY")
        self.assertEqual(result["secondary_date_fixture_count"], 0)

    def test_same_day_shared_team_does_not_match(self):
        result = verify([self.primary], [self.other], "2026-11-22")
        self.assertEqual(result["matched"], 0)
        self.assertEqual(result["unmatched"], 1)
        detail = result["unmatched_details"][0]
        self.assertEqual(detail["source_presence_status"], "SECONDARY_SAME_DAY_SHARED_TEAM")
        self.assertEqual(detail["secondary_shared_team_count"], 1)

    def test_same_day_unrelated_fixture(self):
        unrelated = dict(self.other, home="Bayern Munich")
        result = secondary_presence_diagnostic(self.primary, [unrelated], "2026-11-22")
        self.assertEqual(result["source_presence_status"], "SECONDARY_DATE_PRESENT_NO_TEAM_MATCH")

    def test_diagnostic_never_approves_conflicting_opponent(self):
        result = verify([self.primary], [self.other], "2026-11-22")
        self.assertNotEqual(result["status"], "VERIFIED")
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["unmatched_details"][0]["reason"], "not_found")

    def test_future_secondary_excluded(self):
        result = secondary_presence_diagnostic(self.primary, [self.other], "2026-11-07")
        self.assertEqual(result["source_presence_status"], "SECONDARY_DATE_EMPTY")


if __name__ == "__main__":
    unittest.main()
