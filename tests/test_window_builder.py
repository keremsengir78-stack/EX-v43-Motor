import unittest

from ex_window_builder import build_windows


def record(i, season="2026", venue="home"):
    return {"fixture_id": str(i), "kickoff_at": "2026-01-%02dT12:00:00Z" % (i + 1),
            "season": season, "venue": venue, "verified": True, "source": "audited",
            "goals_for": 2, "goals_against": 1}


def sample():
    rows = [record(i) for i in range(12)]
    rows += [record(12, "2025"), record(13, "2025")]
    rows += [record(14, "2026", "away")]
    return rows


class WindowBuilderTests(unittest.TestCase):
    def test_windows_are_sorted_and_overlapping(self):
        result = build_windows(list(reversed(sample())), "home", "2026", "2025", "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "WINDOWS_READY")
        windows = result["windows"]
        self.assertEqual(len(windows["venue_last5"]), 5)
        self.assertEqual(len(windows["venue_last10"]), 10)
        self.assertEqual(len(windows["current_season"]), 13)
        self.assertEqual(len(windows["previous_venue"]), 2)
        self.assertEqual([x["fixture_id"] for x in windows["venue_last5"]],
                         [x["fixture_id"] for x in windows["venue_last10"][:5]])
        self.assertFalse(result["ex_final_allowed"])

    def test_duplicate_blocks(self):
        rows = sample()
        rows.append(dict(rows[0]))
        result = build_windows(rows, "home", "2026", "2025", "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("record:15:duplicate_or_missing_fixture", result["issues"])

    def test_future_fixture_blocks(self):
        result = build_windows(sample(), "home", "2026", "2025", "2026-01-10T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("date_invalid_or_future" in issue for issue in result["issues"]))

    def test_missing_previous_season_blocks(self):
        rows = [row for row in sample() if row["season"] != "2025"]
        result = build_windows(rows, "home", "2026", "2025", "2026-02-01T00:00:00Z")
        self.assertIn("previous_venue:sample_incomplete", result["issues"])

    def test_unverified_fixture_blocks(self):
        rows = sample()
        rows[0]["verified"] = False
        result = build_windows(rows, "home", "2026", "2025", "2026-02-01T00:00:00Z")
        self.assertIn("record:0:unverified", result["issues"])


if __name__ == "__main__":
    unittest.main()
