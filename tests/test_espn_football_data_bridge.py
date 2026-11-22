import unittest
from unittest.mock import patch
from ex_espn_football_data_bridge import compare_espn_football_data, fetch_and_compare_historical_day


def match(home_goals=2, away_goals=1, home="Arsenal", away="Chelsea"):
    return {"date": "2026-01-01", "league": "en.1", "home": home, "away": away,
            "home_goals": home_goals, "away_goals": away_goals}


class ESPNFootballDataBridgeTests(unittest.TestCase):
    def _run(self, espn=None, secondary=None):
        primary = [match()] if espn is None else espn
        second = [match()] if secondary is None else secondary
        with patch("ex_espn_provider.fetch_espn_scoreboard",
                   return_value=(primary, {"provider": "ESPN", "sha256": "abc"})) as fetch:
            with patch("ex_cross_verify.secondary_rows",
                       return_value=(second, {"provider": "football-data.co.uk"})) as csv:
                result = fetch_and_compare_historical_day(
                    "en.1", "2025-2026", "2026-01-01", "2026-02-01")
        return result, fetch, csv

    def test_two_provider_fetch_matches_provisionally(self):
        result, fetch, csv = self._run()
        self.assertEqual(result["status"], "PROVISIONAL_MATCH_UNAUDITED")
        self.assertEqual(result["comparison"]["matched"], 1)
        self.assertEqual(result["provenance"]["espn"]["provider"], "ESPN")
        fetch.assert_called_once()
        csv.assert_called_once()

    def test_two_provider_fetch_reports_conflict(self):
        result, _, _ = self._run(secondary=[match(4, 1)])
        self.assertEqual(result["status"], "SCORE_CONFLICT")
        self.assertFalse(result["ex_final_allowed"])

    def test_two_provider_fetch_rejects_empty_day(self):
        result, _, _ = self._run(secondary=[])
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("football_data:missing_or_invalid_day", result["issues"])

    def test_two_provider_fetch_rejects_unsupported_league_before_network(self):
        with patch("ex_espn_provider.fetch_espn_scoreboard") as fetch:
            result = fetch_and_compare_historical_day(
                "xx.1", "2025-2026", "2026-01-01", "2026-02-01")
        self.assertEqual(result["status"], "BLOCKED")
        fetch.assert_not_called()

    def test_two_provider_fetch_rejects_cutoff_before_network(self):
        with patch("ex_espn_provider.fetch_espn_scoreboard") as fetch:
            result = fetch_and_compare_historical_day(
                "en.1", "2025-2026", "2026-02-01", "2026-02-01")
        self.assertEqual(result["status"], "BLOCKED")
        fetch.assert_not_called()

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
