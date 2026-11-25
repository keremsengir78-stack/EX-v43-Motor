import datetime as dt
import unittest

from ex_auto_control import auto_control
from ex_decision import MARKETS, assess_pup
from ex_engine import audit
from ex_leagues import APPROVED_LEAGUES, season_bounds, season_range
from run_ex_league_coverage import coverage


class ApprovedLeaguesTests(unittest.TestCase):
    def test_norway_and_dutch_season_boundaries(self):
        day = dt.date(2026, 4, 10)
        self.assertEqual((dt.date(2026, 1, 1), dt.date(2025, 1, 1)), season_bounds("no.1", day))
        self.assertEqual((dt.date(2025, 7, 1), dt.date(2024, 7, 1)), season_bounds("nl.2", day))
        self.assertEqual((dt.date(2025, 1, 1), dt.date(2026, 1, 1)), season_range("no.1", "2025"))

    def test_approved_scope_covers_all_13_competitions(self):
        result = coverage({"leagues": {}})
        self.assertEqual(13, len(APPROVED_LEAGUES))
        self.assertEqual([], result["approved_scope_gaps"])
        for code in APPROVED_LEAGUES:
            self.assertTrue(result["registered_leagues"][code]["main_ingestion"])
            self.assertIsNotNone(result["registered_leagues"][code]["calendar_and_odds_adapter"])

    def test_norway_tur2_autocontrol_and_pup_keep_research_separate(self):
        fixture = {"league": "no.1", "date": "2026-04-10", "home": "A", "away": "B"}
        rows = [dict(league="no.1", date=dt.date.fromisoformat(day), home="A", away="B", hg=3, ag=1)
                for day in ("2025-08-01", "2026-03-04", "2026-04-10", "2026-04-11")]
        result, = audit(rows, [fixture])
        self.assertTrue(result["recompute_consistent"])
        self.assertEqual(["2026-03-04"], result["samples"]["home"]["match_dates"][2])
        self.assertEqual(["2025-08-01"], result["samples"]["home"]["match_dates"][3])
        self.assertTrue(set(MARKETS).issubset(result["market_baselines_pct"]))
        premature = auto_control(result)
        self.assertFalse(premature["ex_final_allowed"])
        self.assertNotIn("tur2:recompute_mismatch", premature["issues"])
        decision = assess_pup({}, {}, result["baseline"], "2026-04-10T12:00:00Z", requested=True)
        self.assertEqual("BLOCKED", decision["pup"]["status"])
        self.assertEqual(set(MARKETS), set(decision["markets"]))
        self.assertIsNotNone(decision["pup"]["score_scenarios"])
        self.assertFalse(decision["ex_final_allowed"])
