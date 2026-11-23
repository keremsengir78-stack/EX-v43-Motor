import unittest
from ex_ingestion_to_match_bridge import prepare_ingested_records


class IngestionToMatchBridgeTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{"date": "2026-11-21", "league": "en.1", "home": "A", "away": "B",
                      "home_goals": "2", "away_goals": "1", "season": "2026-27",
                      "source": "OpenFootball"}]
        self.fixtures = [{"fixture_id": "next-A", "league": "en.1", "team": "A"},
                         {"fixture_id": "next-B", "league": "en.1", "team": "B"}]

    def test_home_away_perspective_and_fail_closed(self):
        report = prepare_ingested_records(self.rows, self.fixtures)
        self.assertEqual(report["fixture_count"], 2)
        self.assertEqual(report["historical_records_staged"], 2)
        self.assertEqual(report["results"][0]["historical_staging"][0]["goals_for"], 2)
        self.assertEqual(report["results"][1]["historical_staging"][0]["goals_for"], 1)
        self.assertFalse(report["ex_final_allowed"])

    def test_no_invented_kickoff_or_verification(self):
        record = prepare_ingested_records(self.rows, self.fixtures)["results"][0]["historical_staging"][0]
        self.assertIsNone(record["kickoff_at"])
        self.assertFalse(record["verified"])

    def test_unmatched_team_is_blocked(self):
        result = prepare_ingested_records(self.rows, [{"fixture_id": "x", "league": "en.1", "team": "C"}])
        self.assertIn("historical:no_matching_records", result["results"][0]["issues"])

    def test_bad_score_rejected_without_crash(self):
        self.rows[0]["home_goals"] = "unknown"
        result = prepare_ingested_records(self.rows, self.fixtures)
        self.assertIn("historical:invalid_score", result["results"][0]["issues"])
        self.assertEqual(result["historical_records_staged"], 0)

    def test_invalid_fixture_rejected(self):
        with self.assertRaises(ValueError):
            prepare_ingested_records(self.rows, [{"league": "en.1", "team": "A"}])


if __name__ == "__main__":
    unittest.main()
