from datetime import datetime, timedelta, timezone
import unittest

from ex_decision import MARKETS
from ex_model_optimization import evaluate, measure, score


class OptimizationTests(unittest.TestCase):
    def test_missing_external_is_not_an_observed_zero(self):
        row = {"strength": dict.fromkeys(MARKETS, .6), "kickoff_workload": (0, .2, 0, .2), "external": None}
        model = {"name": "A", "parameters": {m: {"workload": [0] * 5, "external": [0] * 4} for m in MARKETS}}
        self.assertIsNone(score(model, row, "MS1"))
        row["external"] = (0, 0, 0)
        self.assertAlmostEqual(.55, score(model, row, "MS1"))

    def test_late_labels_are_purged_and_high_probability_count_is_reported(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        rows = []
        for i in range(168):
            day = start + timedelta(days=i)
            rows.append({"kickoff": day, "finished": day + timedelta(hours=2),
                         "strength": dict.fromkeys(MARKETS, (i % 2) * .6 + .2),
                         "labels": dict.fromkeys(MARKETS, i % 2), "league": "tr.1"})
        rows[10]["finished"] = start + timedelta(days=90)
        result = evaluate(rows, ("STAT_FORM",))
        self.assertEqual([83, 42, 42], result["splits"])
        report, _ = measure(rows[:2], [.69, .70], "MS1")
        self.assertEqual(1, report["predictions_at_least_70_pct"])
        self.assertEqual(1, report["hit_rate_at_least_70_pct"])
