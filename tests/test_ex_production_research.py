import datetime as dt
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ex_history_archive import HistoryArchive, utc
from ex_official_minutes import minutes_from_timeline
from ex_pregame_weather import forecast
from run_ex_prospective_validation import evaluate, join_holdout


class ProductionResearchTests(unittest.TestCase):
    def test_official_match_timeline_reconciles_both_team_totals(self):
        fixtures = [json.loads(path.read_text()) for path in (
            Path("research/ucl/domestic-minutes-pilot.json"),
            Path("research/ucl/domestic-minutes-czech-pilot.json"),
        )]
        for fixture in fixtures:
            for team in fixture["teams"].values():
                result = minutes_from_timeline(team["starters"], team["substitutions"])
                self.assertEqual(990, sum(result.values()))
                self.assertEqual(16, len(result))
        self.assertEqual(8, minutes_from_timeline(**fixtures[0]["teams"]["home"])["Alaa Ghram"])

    def test_invalid_substitution_is_rejected(self):
        with self.assertRaises(ValueError):
            minutes_from_timeline([f"Starter{i}" for i in range(11)], [(14, "Not active", "Reserve")])

    def test_original_fixture_and_late_forecast_are_rejected(self):
        markets = ("KG_VAR", "2.5_UST", "MS1", "MS2")
        kickoff = "2026-11-26T19:00:00Z"
        model = {"original_ids": ["old"], "original_last_kickoff": "2026-11-24T09:00:00Z",
                 "frozen_at": "2026-11-24T19:00:00Z", "coefficients": {"KG_VAR": [0, 1], "2.5_UST": [0, 1]}}
        row = {"event_id": "new", "kickoff": kickoff, "forecast_at": "2026-11-26T17:00:00Z",
               "finished": "2026-11-26T21:00:00Z", "short": dict.fromkeys(markets, .5),
               "labels": dict.fromkeys(markets, 1)}
        result = evaluate(model, [row])
        self.assertFalse(result["production_allowed"])
        self.assertEqual("REFERENCE_ONLY", result["markets"]["MS1"]["calibration"])
        for changed in ({"event_id": "old"}, {"forecast_at": kickoff}):
            with self.assertRaises(ValueError):
                evaluate(model, [{**row, **changed}])

    def test_holdout_rejects_labels_in_forecast_ledger(self):
        row = {"event_id": "1", "kickoff": "2026-11-25T19:00:00Z", "teams": {"home": "A", "away": "B"}}
        outcome = {**row, "finished": "2026-11-25T21:00:00Z", "settled_at": "2026-11-26T00:00:00Z",
                   "labels": {"KG_VAR": 1}}
        self.assertEqual(1, join_holdout([row], [outcome])[0]["labels"]["KG_VAR"])
        with self.assertRaises(ValueError):
            join_holdout([{**row, "labels": {}}], [outcome])

    def test_forecast_is_limited_to_pregame_and_correct_hour(self):
        stamp = utc("2026-11-24T18:00:00Z")
        args = {"latitude": 51.48, "longitude": -.19, "utc_offset_seconds": 0,
                "hourly_units": {"temperature_2m": "°C", "precipitation_probability": "%", "wind_speed_10m": "km/h"},
                "hourly": {"time": ["2026-11-25T19:00"], "temperature_2m": [10],
                           "precipitation_probability": [40], "wind_speed_10m": [12]}}
        with TemporaryDirectory() as root:
            archive = HistoryArchive(root, 1, fetch=lambda url: json.dumps(args).encode(), clock=lambda: stamp)
            kickoff = "2026-11-25T19:15:00Z"
            observation = forecast(archive, (51.48, -.19), kickoff,
                                   lambda: (stamp + dt.timedelta(seconds=1)).isoformat())
            self.assertEqual("PREMATCH_NUMERICAL_FORECAST", observation["kind"])
            with self.assertRaises(ValueError):
                forecast(archive, (51.48, -.19), kickoff, lambda: kickoff)

    def test_official_review_does_not_certify_upstream_lineage(self):
        from run_ex_official_score_review import reconcile

        official = json.loads(Path("research/ucl/dfl-score-review.json").read_text())
        date, home, away, hg, ag = official["fixtures"][0]
        staged = [{"date": date, "home": home, "away": away, "home_goals": hg, "away_goals": ag,
                   "league": "de.1", "season": "2026-27"}]
        ledger = {"queues": {"newer": {"provisional_matches": staged}}}
        output = reconcile(official, staged, ledger)
        self.assertEqual(1, output["matches"]["ESPN"])
        self.assertFalse(output["provider_lineage_certified"])

    def test_context_sensitivity_preserves_unknown_weight_and_lock(self):
        from run_ex_ucl_pregame import conditional_context_range

        interval = conditional_context_range(.6)
        self.assertAlmostEqual(.3, interval["lower_weighted_score"])
        self.assertAlmostEqual(.8, interval["upper_weighted_score"])
        self.assertEqual(["match_conditions", "external_factors"], interval["unknown_components"])
        self.assertFalse(interval["ex_final_allowed"])
