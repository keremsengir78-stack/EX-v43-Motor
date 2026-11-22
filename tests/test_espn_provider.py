import unittest
from ex_espn_provider import parse_espn_scoreboard


def event(home=2, away=1):
    return {"date": "2026-01-01T12:00:00Z",
            "status": {"type": {"completed": True}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "team": {"displayName": "Home"}, "score": home},
                {"homeAway": "away", "team": {"displayName": "Away"}, "score": away}
            ]}]}


def parse(events):
    return parse_espn_scoreboard({"events": events}, "en.1", "2026-02-01")


class ESPNMalformedTests(unittest.TestCase):
    def test_requested_day_filters_other_dates(self):
        first, second = event(), event()
        second["date"] = "2026-01-02T12:00:00Z"
        result = parse_espn_scoreboard({"events": [first, second]}, "en.1",
                                       "2026-02-01", requested_day="2026-01-01")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["date"], "2026-01-01")

    def test_requested_day_accepts_matching_date(self):
        result = parse_espn_scoreboard({"events": [event()]}, "en.1",
                                       "2026-02-01", requested_day="2026-01-01")
        self.assertEqual(len(result), 1)

    def test_requested_day_at_cutoff_rejected(self):
        with self.assertRaises(ValueError):
            parse_espn_scoreboard({"events": [event()]}, "en.1",
                                  "2026-02-01", requested_day="2026-02-01")

    def test_invalid_requested_day_rejected(self):
        with self.assertRaises(ValueError):
            parse_espn_scoreboard({"events": [event()]}, "en.1",
                                  "2026-02-01", requested_day="invalid")

    def test_no_requested_day_preserves_legacy_parser(self):
        first, second = event(), event()
        second["date"] = "2026-01-02T12:00:00Z"
        self.assertEqual(len(parse([first, second])), 2)

    def test_identical_duplicate_match_deduplicated(self):
        self.assertEqual(len(parse([event(), event()])), 1)

    def test_conflicting_duplicate_match_blocks(self):
        with self.assertRaisesRegex(ValueError, "conflicting ESPN scores"):
            parse([event(2, 1), event(3, 1)])

    def test_duplicate_team_case_variants_deduplicated(self):
        first, second = event(), event()
        second["competitions"][0]["competitors"][0]["team"]["displayName"] = "HOME"
        self.assertEqual(len(parse([first, second])), 1)

    def test_malformed_date_does_not_crash_other_results(self):
        bad = event()
        bad["date"] = "invalid"
        self.assertEqual(len(parse([bad, event()])), 1)

    def test_different_match_scores_are_independent(self):
        first, second = event(), event(3, 0)
        second["competitions"][0]["competitors"][0]["team"]["displayName"] = "Other"
        self.assertEqual(len(parse([first, second])), 2)

    def test_non_dict_event_skipped(self):
        self.assertEqual(len(parse([None, event()])), 1)

    def test_non_list_competitions_skipped(self):
        bad = event()
        bad["competitions"] = None
        self.assertEqual(len(parse([bad, event()])), 1)

    def test_missing_status_skipped(self):
        bad = event()
        bad["status"] = None
        self.assertEqual(len(parse([bad, event()])), 1)

    def test_boolean_score_rejected(self):
        self.assertEqual(parse([event(True, 1)]), [])

    def test_non_numeric_score_rejected(self):
        self.assertEqual(parse([event("2.0", 1)]), [])

    def test_valid_numeric_string_score_accepted(self):
        result = parse([event("2", "1")])
        self.assertEqual((result[0]["home_goals"], result[0]["away_goals"]), (2, 1))


if __name__ == "__main__":
    unittest.main()
