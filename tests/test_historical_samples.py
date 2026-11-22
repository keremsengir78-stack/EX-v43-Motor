import unittest
from ex_historical_samples import historical_metric


def match(i, value=2):
    return {"fixture_id": "fixture-%d" % i, "kickoff_at": "2026-01-%02dT12:00:00Z" % (i + 1),
            "source": "audited-fixture", "verified": True, "goals_for": value}


def windows():
    venue = [match(i) for i in range(9, -1, -1)]
    return {"venue_last5": venue[:5], "venue_last10": venue,
            "current_season": [match(15), match(14)],
            "previous_venue": [match(13), match(12)]}


class HistoricalSamplesTests(unittest.TestCase):
    def test_weighted_metric_not_probability(self):
        data = windows()
        result = historical_metric(data, "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "HISTORICAL_EVIDENCE_ONLY")
        self.assertEqual(result["weighted_metric"], 2)
        self.assertIsNone(result["calibrated_probability"])
        self.assertFalse(result["ex_final_allowed"])

    def test_missing_five_blocks(self):
        data = windows()
        data["venue_last5"].pop()
        self.assertIn("venue_last5:sample_incomplete", historical_metric(data, "2026-02-01T00:00:00Z")["issues"])

    def test_inconsistent_windows_block(self):
        data = windows()
        data["venue_last5"][0] = match(11)
        self.assertIn("venue_windows:inconsistent", historical_metric(data, "2026-02-01T00:00:00Z")["issues"])

    def test_future_match_blocks(self):
        data = windows()
        self.assertIn("venue_last5:date_invalid_or_future",
                      historical_metric(data, "2026-01-05T00:00:00Z")["issues"])

    def test_unverified_source_blocks(self):
        data = windows()
        data["current_season"][0]["verified"] = False
        self.assertIn("current_season:source_unverified",
                      historical_metric(data, "2026-02-01T00:00:00Z")["issues"])

    def test_unsorted_window_blocks(self):
        data = windows()
        data["venue_last10"].reverse()
        self.assertIn("venue_last10:not_latest_first",
                      historical_metric(data, "2026-02-01T00:00:00Z")["issues"])

    def test_duplicate_fixture_blocks(self):
        data = windows()
        data["previous_venue"][1] = dict(data["previous_venue"][0])
        self.assertIn("previous_venue:fixture_duplicate_or_missing",
                      historical_metric(data, "2026-02-01T00:00:00Z")["issues"])


if __name__ == "__main__":
    unittest.main()
