import unittest
from ex_cross_verify import reviewed_name, verify
from ex_live_bridge_batch import REVIEWED_ALIASES


class ObservedAliasTests(unittest.TestCase):
    def test_six_source_observed_name_pairs(self):
        pairs = (
            ("es.1", "Real Betis", "Betis"),
            ("es.1", "Celta Vigo", "Celta"),
            ("es.1", "Atlético Madrid", "Ath Madrid"),
            ("de.1", "VfB Stuttgart", "Stuttgart"),
            ("en.1", "Manchester United", "Man United"),
            ("en.1", "Leeds United", "Leeds"),
        )
        for league, primary, secondary in pairs:
            with self.subTest(primary=primary):
                self.assertEqual(
                    reviewed_name(primary, league, REVIEWED_ALIASES),
                    reviewed_name(secondary, league, REVIEWED_ALIASES))

    def test_alias_never_ignores_score_conflict(self):
        primary = [{"date": "2026-11-08", "league": "es.1",
                    "home": "Elche", "away": "Real Betis",
                    "home_goals": 2, "away_goals": 1}]
        secondary = [{"date": "2026-11-08", "league": "es.1",
                      "home": "Elche", "away": "Betis",
                      "home_goals": 0, "away_goals": 1}]
        result = verify(primary, secondary, "2026-11-22", REVIEWED_ALIASES)
        self.assertEqual(result["matched"], 1)
        self.assertEqual(len(result["conflicts"]), 1)
        self.assertEqual(result["status"], "CONFLICT")

    def test_alias_does_not_match_wrong_opponent(self):
        primary = [{"date": "2026-11-08", "league": "es.1",
                    "home": "Elche", "away": "Real Betis",
                    "home_goals": 2, "away_goals": 1}]
        secondary = [{"date": "2026-11-08", "league": "es.1",
                      "home": "Elche", "away": "Barcelona",
                      "home_goals": 2, "away_goals": 1}]
        result = verify(primary, secondary, "2026-11-22", REVIEWED_ALIASES)
        self.assertEqual(result["matched"], 0)


if __name__ == "__main__":
    unittest.main()
