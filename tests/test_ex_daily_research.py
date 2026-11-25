import datetime as dt
import unittest

from ex_cross_verify import norm
from ex_daily_official import key
from ex_daily_research import daily_analysis
from ex_decision import MARKETS
from ex_history_archive import utc


class DailyResearchTests(unittest.TestCase):
    def test_ucl_domestic_archive_remains_separate_from_prospective_calibration(self):
        cutoff = utc("2026-11-25T09:00:00Z")
        kickoff = utc("2026-11-25T20:00:00Z")
        fixture = {"league": "UCL", "home": "Club A", "away": "Club B",
                   "date": "2026-11-25", "kickoff_at": kickoff.isoformat()}
        teams = {norm("Club A"): "Club A", norm("Club B"): "Club B"}
        leagues = {"Club A": "en.1", "Club B": "de.1"}
        rows = []
        for year in (2025, 2026):
            for index in range(1, 11):
                date = dt.date(year, 9, index)
                rows += [{"date": date, "league": "en.1", "home": "Club A", "away": "other", "hg": 2, "ag": 1},
                         {"date": date, "league": "de.1", "home": "other", "away": "Club B", "hg": 1, "ag": 2}]
        fixture_scope = {(kickoff, "Club A", "Club B")}
        snapshot = rows, [], teams, leagues, fixture_scope
        result = daily_analysis(fixture, None, snapshot, cutoff)
        self.assertEqual("UNCALIBRATED_CROSS_LEAGUE_BASELINE", result["domestic_research"]["status"])
        self.assertTrue(result["tur2"])
        self.assertIsNone(result["calibration_cohort"])
        self.assertEqual(set(MARKETS), set(result["markets"]["markets"]))
        self.assertTrue(all(m["ex_g"]["probability"] is None for m in result["markets"]["markets"].values()))
        self.assertFalse(result["auto_control"]["ex_final_allowed"])
        self.assertIsNone(daily_analysis({**fixture, "home": "Different"}, None, snapshot, cutoff)["domestic_research"])

    def test_official_aliases_preserve_date_and_orientation(self):
        match = key("en.1", "2026-11-25", "Manchester United", "Spurs")
        self.assertEqual(match, key("en.1", "2026-11-25", "Man United", "Tottenham"))
        self.assertNotEqual(match, key("en.1", "2026-11-25", "Tottenham", "Man United"))
        self.assertNotEqual(match, key("en.1", "2026-11-26", "Man United", "Tottenham"))
