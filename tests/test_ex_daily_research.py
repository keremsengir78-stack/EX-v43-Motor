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
        self.assertNotIn("pup:unverified", result["auto_control"]["issues"])
        self.assertEqual("NOT_REQUESTED", result["markets"]["pup"]["status"])
        self.assertIsNone(daily_analysis({**fixture, "home": "Different"}, None, snapshot, cutoff)["domestic_research"])

    def test_official_aliases_preserve_date_and_orientation(self):
        match = key("en.1", "2026-11-25", "Manchester United", "Spurs")
        self.assertEqual(match, key("en.1", "2026-11-25", "Man United", "Tottenham"))
        self.assertNotEqual(match, key("en.1", "2026-11-25", "Tottenham", "Man United"))
        self.assertNotEqual(match, key("en.1", "2026-11-26", "Man United", "Tottenham"))

    def test_rolling_history_uses_ids_and_actual_seasons_after_matchday_five(self):
        cutoff = utc("2027-02-16T13:00:00Z")
        fixture = {"league": "UCL", "home": "Changed brand A", "away": "Changed brand B",
                   "date": "2027-02-16", "kickoff_at": "2027-02-16T20:00:00Z",
                   "team_ids": {"home": "123", "away": "456"}}
        by_team = {}
        for team, league, side in (("123", "eng.1", "home"), ("456", "ger.1", "away")):
            games = []
            for year in (2025, 2026):
                for index in range(10, 0, -1):
                    kickoff = utc(f"{year}-09-{index:02}T12:00:00Z")
                    teams = {side: team, "home" if side == "away" else "away": f"other{index}"}
                    games.append({"kickoff": kickoff, "finished": kickoff + dt.timedelta(hours=2),
                                  "captured_at": kickoff + dt.timedelta(hours=3),
                                  "competition": league, "teams": teams, "score": (2, 1)})
            games.append({**games[-1], "captured_at": cutoff, "score": (20, 20),
                          "kickoff": utc("2027-02-13T12:00:00Z")})
            by_team[team] = games
        row = daily_analysis(fixture, None, None, cutoff, by_team=by_team)
        result = row["domestic_research"]
        self.assertEqual("ROLLING_DOMESTIC_PROVIDER_TEAM_ID", result["history_scope"])
        self.assertEqual({"home": "en.1", "away": "de.1"}, result["domestic_leagues"])
        self.assertEqual("2026-09-10", result["samples"]["home"]["match_dates"][0][-1])
        self.assertTrue(row["tur2"])
        self.assertIsNone(row["calibration_cohort"])

    def test_official_fixture_and_odds_checks_are_market_scoped(self):
        cutoff = utc("2026-11-25T13:00:00Z")
        board = {"url": "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard?dates=20261125",
                 "retrieved_at": "2026-11-25T12:59:00Z", "sha256": "1" * 64}
        fixture = {"league": "UCL", "home": "Sabah FK", "away": "Barcelona", "date": "2026-11-25",
                   "kickoff_at": "2026-11-25T17:45:00Z", "fixture_source": board["url"],
                   "fixture_checked_at": board["retrieved_at"]}
        quotes = [{"market": "MS1", "bookmaker": "DraftKings", "decimal_odds": 2,
                   "observed_at": board["retrieved_at"], "source": board["url"]}]
        row = daily_analysis(fixture, None, None, cutoff, quotes=quotes, board_evidence=board)
        self.assertEqual("FIXTURE_CROSS_VERIFIED", row["fixture_evidence"]["status"])
        self.assertNotIn("odds_lock:blocked", row["auto_control_by_market"]["MS1"]["issues"])
        self.assertIn("odds_lock:blocked", row["auto_control_by_market"]["KG_VAR"]["issues"])
        self.assertNotIn("fixture_sources:unverified", row["auto_control_by_market"]["MS1"]["issues"])
        self.assertIn("second_source:unverified", row["auto_control_by_market"]["MS1"]["issues"])
        self.assertFalse(row["auto_control_by_market"]["MS1"]["ex_final_allowed"])
        low = daily_analysis(fixture, None, None, cutoff, board_evidence=board,
                             quotes=[{**quotes[0], "decimal_odds": 1.19}])
        self.assertIn("odds_lock:pass_1_19_or_lower", low["auto_control_by_market"]["MS1"]["issues"])
        self.assertNotIn("odds_lock:pass_1_19_or_lower", low["auto_control_by_market"]["KG_VAR"]["issues"])
        reversed_fixture = {**fixture, "home": "Barcelona", "away": "Sabah FK"}
        rejected = daily_analysis(reversed_fixture, None, None, cutoff, board_evidence=board)
        self.assertEqual("UNVERIFIED", rejected["fixture_evidence"]["status"])
