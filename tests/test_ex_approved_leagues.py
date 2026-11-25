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

    def test_main_entry_point_runs_explicit_pup_after_research_markets(self):
        import json
        from pathlib import Path
        import subprocess
        import sys
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            root = Path(directory)
            season = root / "2026-27"
            season.mkdir()
            (season / "en.1.json").write_text(json.dumps({"matches": [
                {"date": day, "team1": "A", "team2": "B", "score": {"ft": [2, 1]}}
                for day in ("2026-06-01", "2026-10-01")
            ]}))
            fixtures = root / "fixtures.csv"
            fixtures.write_text("date,league,home,away,kickoff_at\n2026-11-25,en.1,A,B,2026-11-25T18:00:00Z\n")
            odds = root / "odds.json"
            odds.write_text(json.dumps([{"MS1": {"market": "MS1", "bookmaker": "test",
                                                 "observed_at": "2026-11-25T11:00:00Z",
                                                 "decimal_odds": 1.25, "source": "test"}}]))
            output = root / "out"
            subprocess.run([sys.executable, "ex_one_command.py", "--as-of", "2026-11-25",
                            "--seasons", "2026-27", "--leagues", "en.1", "--offline", directory,
                            "--outdir", str(output), "--fixtures", str(fixtures), "--odds", str(odds),
                            "--no-secondary", "--pup"], check=True, capture_output=True)
            report = json.loads((output / "full_report.json").read_text())
            match, = report["matches"]
            self.assertTrue(match["recompute_consistent"])
            self.assertEqual(set(MARKETS), set(match["market_values"]))
            self.assertEqual("VERIFIED_INPUT", match["market_values"]["MS1"]["odds_lock"]["status"])
            self.assertEqual("BLOCKED", match["auto_control"]["status"])
            self.assertEqual("BLOCKED", match["pup"]["status"])
            self.assertFalse(report["ex_final_allowed"])
