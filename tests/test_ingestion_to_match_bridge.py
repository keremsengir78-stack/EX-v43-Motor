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


    def test_decimal_score_not_truncated(self):
        self.rows[0]["home_goals"] = "2.5"
        result = prepare_ingested_records(self.rows, self.fixtures)
        self.assertEqual(result["historical_records_staged"], 0)
        self.assertIn("historical:invalid_score", result["results"][0]["issues"])

    def test_duplicate_history_is_not_counted_twice(self):
        result = prepare_ingested_records(self.rows * 2, self.fixtures)
        self.assertEqual(result["historical_records_staged"], 2)
        self.assertIn("historical:duplicate_fixture", result["results"][0]["issues"])

    def test_invalid_date_rejected(self):
        self.rows[0]["date"] = "not-a-date"
        result = prepare_ingested_records(self.rows, self.fixtures)
        self.assertEqual(result["historical_records_staged"], 0)
        self.assertIn("historical:invalid_date", result["results"][0]["issues"])

    def test_duplicate_fixture_ids_rejected(self):
        with self.assertRaises(ValueError):
            prepare_ingested_records(self.rows, [self.fixtures[0], self.fixtures[0]])


    def test_as_of_excludes_same_day(self):
        result = prepare_ingested_records(self.rows, self.fixtures, "2026-11-21")
        self.assertEqual(result["historical_records_staged"], 0)
        self.assertIn("historical:future_or_same_day_excluded", result["results"][0]["issues"])

    def test_as_of_includes_earlier_match(self):
        result = prepare_ingested_records(self.rows, self.fixtures, "2026-11-22")
        self.assertEqual(result["historical_records_staged"], 2)

    def test_as_of_rejects_invalid_date(self):
        with self.assertRaises(ValueError):
            prepare_ingested_records(self.rows, self.fixtures, "tomorrow")


    def test_indexed_results_keep_leagues_separate(self):
        other = dict(self.rows[0], league="es.1")
        result = prepare_ingested_records(self.rows + [other], self.fixtures)
        self.assertEqual(result["historical_records_staged"], 2)

    def test_many_teams_only_match_relevant_history(self):
        fixtures = [{"fixture_id": "fixture-" + str(i), "league": "en.1",
                     "team": "T" + str(i)} for i in range(100)]
        fixtures.append(self.fixtures[0])
        result = prepare_ingested_records(self.rows, fixtures)
        self.assertEqual(result["fixture_count"], 101)
        self.assertEqual(result["historical_records_staged"], 1)
        self.assertEqual(result["results"][-1]["historical_record_count"], 1)

    def test_invalid_fixture_rejected(self):
        with self.assertRaises(ValueError):
            prepare_ingested_records(self.rows, [{"league": "en.1", "team": "A"}])


if __name__ == "__main__":
    unittest.main()
