import datetime as dt
import json
import unittest
from pathlib import Path

from ex_engine import distribution
from ex_model_challengers import compare_calibration
from run_ucl_model_integration import context_measurements, score_grid_marginals, timestamp


class ModelIntegrationTests(unittest.TestCase):
    def test_grid_recovers_all_market_marginals(self):
        for rates in ((0, 0), (1.45, .62), (5, 5)):
            original = distribution(*rates)
            independent = score_grid_marginals(*rates)
            for name, value in independent.items():
                self.assertAlmostEqual(original[name], value, places=9)

    def test_only_prematch_events_contribute_to_workload(self):
        kickoff = timestamp("2026-11-24T20:00:00Z")
        captured = timestamp("2026-11-24T10:00:00Z")
        event = {"event_id": "a", "kickoff_at": "2026-11-18T20:00:00Z"}
        news = {"predicted_lineup": "A; B, C", "out": "A (knee, ankle), D (hand)", "doubtful": "None"}
        measurements = context_measurements({"matches_shown": [event]}, news, kickoff, captured)
        self.assertEqual(144, measurements["max_hours_since_latest_match"])
        self.assertEqual(2, measurements["reported_out_count"])
        self.assertEqual(1, measurements["min_matches_in_last_7_days"])
        self.assertIsNone(measurements["confirmed_rotation_changes"])
        with self.assertRaises(ValueError):
            context_measurements({"matches_shown": [{**event, "kickoff_at": kickoff.isoformat()}]},
                                 news, kickoff, captured)

    def test_selection_ignores_test_outcomes_and_early_external_rows(self):
        start = dt.date(2026, 1, 1)
        rows = [(start + dt.timedelta(days=day), .3, i % 2, (0.0, 0.0))
                for day in range(20) for i in range(8)]
        original = compare_calibration(rows, rows)
        changed = [(day, p, 0 if day >= start + dt.timedelta(days=15) else actual, features)
                   for day, p, actual, features in rows]
        updated = compare_calibration(changed, rows)
        self.assertEqual(original["validation_brier"], updated["validation_brier"])
        self.assertEqual(original["selected_on_validation"], updated["selected_on_validation"])
        self.assertEqual(40, updated["external_ucl_transfer"]["eligible_n"])
        self.assertFalse(updated["production_allowed"])

    def test_frozen_real_replay_keeps_odds_separate_from_ex_g(self):
        report = json.loads(Path("reports/ucl_matchday5_model_integration_2026_11_24.json").read_text())
        self.assertEqual(9, len(report["fixtures"]))
        self.assertFalse(report["pup_allowed"])
        for match in report["fixtures"]:
            self.assertTrue(match["tur2_recompute_consistent"])
            self.assertEqual("NO_FINAL", match["decision"])
            for market in match["markets"].values():
                self.assertIsNone(market["ex_g"])
                self.assertIsNone(market["ex_d"])
                self.assertFalse(market["auto_control"]["ex_final_allowed"])
        slovan = next(m for m in report["fixtures"] if m["fixture"]["home"] == "Slovan Bratislava")
        self.assertEqual("2026-11-21", slovan["measurements"]["home"]["latest_domestic_result_date"])
        self.assertEqual(0, slovan["measurements"]["home"]["min_matches_in_last_7_days"])


if __name__ == "__main__":
    unittest.main()
