import unittest
from datetime import date, timedelta

from ex_baseline_calibration import chronological_intercept
from run_ucl_matchday_inputs import market_quotes


class MatchdayInputDataTests(unittest.TestCase):
    def test_exact_total_and_prematch_cutoff(self):
        quote = {
            "provider": {"name": "Book"},
            "moneyline": {"home": {"close": {"odds": "-800"}}, "away": {"close": {"odds": "+500"}}},
            "total": {"over": {"close": {"line": "o3.5", "odds": "-120"}}},
        }
        metadata = {"retrieved_at": "2026-11-24T10:00:00+00:00", "url": "https://example.com", "sha256": "a" * 64}
        cutoff = "2026-11-24T17:45:00Z"
        offers = market_quotes([quote], metadata, cutoff)
        self.assertEqual(["MS1", "MS2"], [offer["market"] for offer in offers])
        self.assertEqual("PASS_ODDS_1_19_OR_LOWER", offers[0]["odds_gate"])
        quote["total"]["over"]["close"]["line"] = "o2.5"
        self.assertEqual(3, len(market_quotes([quote], metadata, cutoff)))
        self.assertEqual([], market_quotes([quote], {**metadata, "retrieved_at": cutoff}, cutoff))

    def test_calibration_keeps_same_date_on_one_side_and_does_not_fit_holdout(self):
        start = date(2026, 1, 1)
        rows = [(start + timedelta(days=day), .2, outcome) for day in range(10) for outcome in [0, 1] * 4 + [0, 0]]
        baseline = chronological_intercept(rows)
        changed_holdout = [(day, p, 1 if day >= start + timedelta(days=7) else y) for day, p, y in rows]
        result = chronological_intercept(changed_holdout)
        self.assertEqual((70, 30), (result["train_n"], result["test_n"]))
        self.assertEqual(baseline["training_log_odds_intercept"], result["training_log_odds_intercept"])
        self.assertNotEqual(baseline["adjusted_brier"], result["adjusted_brier"])
        self.assertFalse(result["calibration_certified"])


if __name__ == "__main__":
    unittest.main()
