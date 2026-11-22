import unittest
from ex_espn_football_data_bridge import compare_espn_football_data


def match(home_goals=2, away_goals=1, home="Arsenal", away="Chelsea"):
    return {"date": "2026-01-01", "league": "en.1", "home": home, "away": away,
            "home_goals": home_goals, "away_goals": away_goals}


class ESPNFootballDataBridgeTests(unittest.TestCase):
    def test_identical_scores_remain_provisional(self):
        result = compare_espn_football_data([match()], [match()], "2026-02-01")
        self.assertEqual(result["status"], "PROVISIONAL_MATCH_UNAUDITED")
        self.assertEqual(result["comparison"]["matched"], 1)
        self.assertFalse(result["ex_final_allowed"])

    def test_conflicting_scores_are_reported(self):
        result = compare_espn_football_data([match()], [match(3, 1)], "2026-02-01")
        self.assertEqual(result["status"], "SCORE_CONFLICT")
        self.assertEqual(len(result["comparison"]["conflicts"]), 1)

    def test_missing_secondary_fixture_remains_partial(self):
        result = compare_espn_football_data([match()], [match(home="Liverpool")], "2026-02-01")
        self.assertEqual(result["status"], "PARTIAL_PROVISIONAL_MATCH")
        self.assertEqual(result["comparison"]["unmatched"], 1)

    def test_future_fixture_blocks_without_comparison(self):
        future = match()
        future["date"] = "2026-02-01"
        result = compare_espn_football_data([future], [match()], "2026-02-01")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["comparison"])

    def test_invalid_score_blocks_without_certification(self):
        bad = match()
        bad["home_goals"] = True
        result = compare_espn_football_data([match()], [bad], "2026-02-01")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ex_final_allowed"])


if __name__ == "__main__":
    unittest.main()
