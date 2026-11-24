import datetime as dt
import unittest

from ex_component_experiment import evaluate_components
from ex_historical_features import HistoricalFeatures


class HistoricalFeatureTests(unittest.TestCase):
    def test_target_and_later_scores_are_invisible_and_away_orientation_is_correct(self):
        start = dt.date(2026, 9, 1)
        rows = [dict(date=start + dt.timedelta(days=i), league="L", home="H", away="A", hg=2, ag=0)
                for i in range(10)]
        cutoff = start + dt.timedelta(days=10)
        original = HistoricalFeatures(rows).fixture("L", "L", "H", "A", cutoff)
        later = [{**rows[0], "date": cutoff + dt.timedelta(days=i), "hg": 0, "ag": 8} for i in range(2)]
        updated = HistoricalFeatures(rows + later).fixture("L", "L", "H", "A", cutoff)
        self.assertEqual(original, updated)
        self.assertEqual(1, updated["home"]["venue_market_frequencies"]["MS1"])
        self.assertEqual(1, updated["away"]["venue_market_frequencies"]["MS1"])
        self.assertEqual(-2, updated["away"]["venue_goal_difference_last_10"])
        self.assertEqual(10, updated["away"]["domestic_matches_last_14_days"])
        self.assertIsNone(updated["external_factors_score"])

    def test_holdout_labels_do_not_affect_selection(self):
        start = dt.date(2026, 1, 1)
        signals = {name: (0.0, 0.0) for name in ("venue_rates", "recent_goal_form", "domestic_workload")}
        data = [(start + dt.timedelta(days=day), .35, i % 2, signals)
                for day in range(20) for i in range(8)]
        baseline = evaluate_components(data)
        changed = [(day, p, 1 if day >= start + dt.timedelta(days=15) else y, x) for day, p, y, x in data]
        revised = evaluate_components(changed)
        self.assertEqual(baseline["validation_brier"], revised["validation_brier"])
        self.assertEqual(baseline["selected_on_validation"], revised["selected_on_validation"])
        self.assertNotEqual(baseline["test_selected_brier"], revised["test_selected_brier"])
        self.assertFalse(revised["production_allowed"])
