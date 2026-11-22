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
