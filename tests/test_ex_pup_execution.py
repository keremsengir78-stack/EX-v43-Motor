import unittest
from unittest.mock import patch

from ex_decision import MARKETS, assess_pup
from ex_pup_gate import score_scenarios


class PupExecutionTests(unittest.TestCase):
    def setUp(self):
        self.when = "2026-11-25T17:00:00Z"
        self.model = {"lambda_home": 1.8, "lambda_away": 0.6}
        self.quotes = {
            market: {"market": market, "decimal_odds": 1.20 if market == "2.5_UST" else 1.19,
                     "bookmaker": "fixture", "observed_at": "2026-11-25T16:55:00Z", "source": "test"}
            for market in MARKETS
        }

    def run_pup(self, requested=True):
        def calibrated(market, _):
            return {"status": "EX_G_AVAILABLE", "market": market,
                    "probability": 0.9 if market == "MS1" else 0.5, "issues": []}

        with patch("ex_decision.ex_g_from_evidence", side_effect=calibrated):
            return assess_pup({}, self.quotes, self.model, self.when, requested=requested)

    def test_explicit_request_does_not_recompute_or_change_independent_market_results(self):
        inactive, active = self.run_pup(False), self.run_pup()
        self.assertEqual(inactive["markets"], active["markets"])
        self.assertEqual(inactive["values"], active["values"])
        self.assertEqual("NOT_REQUESTED", inactive["pup"]["status"])
        self.assertEqual("2.5_UST", active["pup"]["selection"])
        self.assertEqual("PASS_ODDS_1_19_OR_LOWER", active["pup"]["market_reasons"]["MS1"])
        self.assertLess(active["values"]["2.5_UST"]["ex_d"], 0)
        self.assertEqual("NEGATIVE_EX_D_IS_NOT_A_PASS_RULE", active["pup"]["market_reasons"]["2.5_UST"])
        self.assertFalse(active["ex_final_allowed"])

    def test_unspecified_order_and_odds_gap_require_review(self):
        self.quotes["MS1"]["decimal_odds"] = 1.5
        comparison = self.run_pup()["pup"]
        self.assertEqual("REVIEW_REQUIRED", comparison["status"])
        self.assertIsNone(comparison["selection"])
        self.assertFalse(comparison["pup_allowed"])
        self.quotes["MS1"]["decimal_odds"] = 1.195
        comparison = self.run_pup()["pup"]
        self.assertEqual("BLOCKED", comparison["status"])
        self.assertIn("MS1:price_rule_undefined", comparison["issues"])

    def test_truthy_string_is_not_a_pup_request(self):
        self.assertEqual("NOT_REQUESTED", self.run_pup("true")["pup"]["status"])

    def test_partition_retains_all_scenario_probability_mass(self):
        result = score_scenarios(1.8, .6)
        self.assertAlmostEqual(1, sum(result[k] for k in ("over25_only", "btts_only", "both", "neither")))
        self.assertGreater(result["over25_only"], result["exact_scores"]["3-0"])
        self.assertEqual({"KG_VAR": False, "2.5_UST": True}, result["exclusive_events"]["3-0"])
        self.assertEqual({"KG_VAR": True, "2.5_UST": False}, result["exclusive_events"]["1-1"])
