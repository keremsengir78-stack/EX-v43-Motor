import datetime as dt
import json
from unittest import TestCase
from unittest.mock import Mock

from ex_history_archive import utc
from run_ex_live_evidence_refresh import review_capture


class LiveEvidenceRefreshTests(TestCase):
    def test_requires_both_captures_inside_live_window_and_before_kickoff(self):
        kickoff = utc("2026-11-29T18:00:00Z")
        competition = {"id": "1", "date": kickoff.isoformat(),
                       "competitors": [{"homeAway": side, "id": identifier, "team": {"id": identifier}}
                                       for side, identifier in (("home", "10"), ("away", "20"))],
                       "status": {"type": {"state": "pre"}}}
        board = {"leagues": [{"slug": "eng.1"}],
                 "events": [{**competition, "competitions": [competition]}]}
        detail = {"header": {"id": "1", "competitions": [competition]},
                  "rosters": [{"team": {"id": "10"}}]}
        fixture = {"event_id": "1", "league": "en.1",
                   "kickoff_at": kickoff.isoformat(), "team_ids": {"home": "10", "away": "20"}}
        manifest = {"day": "2026-11-29", "reports": {"en.1": {"board": {"url": "board", "retrieved_at": kickoff.isoformat()},
                    "records": [{"event_id": "1", "source": {"url": "summary", "retrieved_at": kickoff.isoformat()}}]}}}
        start = kickoff - dt.timedelta(hours=48)
        for captures, cutoff, expected in (((start, start), start + dt.timedelta(seconds=1), 1),
                ((start, start - dt.timedelta(seconds=1)), start + dt.timedelta(seconds=1), 0),
                ((start, start), kickoff, 0)):
            cache = Mock()
            cache._load.side_effect = [(json.dumps(x), when) for x, when in zip((board, detail), captures)]
            rows, issues = review_capture(manifest, cache, {"1": fixture}, cutoff)
            self.assertEqual(expected, len(rows))
            self.assertEqual(1 - expected, len(issues))
            if rows:
                self.assertEqual(0, rows[0]["player_roster_entries_observed"])
                self.assertFalse(rows[0]["ex_final_allowed"])

    def test_fractional_research_price_requires_exact_market_and_total(self):
        from run_ucl_matchday_inputs import fractional_research_quotes

        source = {"url": "https://site.api.espn.com/summary", "sha256": "a" * 64,
                  "retrieved_at": "2026-11-27T12:00:00Z"}
        team = {"preMatchFullTimeResultHome": {"value": "4/6"},
                "preMatchGoalLineOver": {"value": "17/20"},
                "preMatchDoubleChanceHomeOrDraw": {"value": "2/11"},
                "preMatchOverUnderHandicap": {"value": "3"}}
        quote = {"provider": {"name": "Bet 365"}, "bettingOdds": {"teamOdds": team}}
        self.assertEqual(["MS1"], [r["market"] for r in fractional_research_quotes([quote], source)])
        team["preMatchOverUnderHandicap"]["value"] = "2.5"
        rows = fractional_research_quotes([quote], source)
        self.assertEqual(["MS1", "2.5_UST"], [r["market"] for r in rows])
        self.assertTrue(all(r["published_at"] is None for r in rows))

    def test_short_window_is_explicitly_incomplete_even_without_calibration(self):
        from ex_auto_control import auto_control

        result = auto_control({"status": "BASELINE_ONLY", "full_historical_windows": False})
        self.assertIn("historical_samples:incomplete", result["issues"])
        self.assertIn("exg:uncalibrated", result["issues"])
        self.assertFalse(result["ex_final_allowed"])
