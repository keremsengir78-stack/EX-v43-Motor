"""Decision-layer regression: independent 50/30/20 market evidence is not a probability."""
import unittest

from ex_decision import MARKETS, assess_markets, weighted_evidence


def features(team=0.8, conditions=0.6, external=0.5):
    return {
        name: {"score": score, "verified": True, "source": "independent-audit",
               "timestamp": "2026-11-21T09:00:00Z"}
        for name, score in (
            ("team_strength", team), ("match_conditions", conditions),
            ("external_factors", external))
    }


class DecisionMarketSafetyTests(unittest.TestCase):
    def test_weighted_score_is_not_calibrated_probability(self):
        result = weighted_evidence(features(), as_of="2026-11-22")
        self.assertEqual(result["weighted_score"], 0.68)
        self.assertEqual(result["contributions"],
                         {"team_strength": 0.4, "match_conditions": 0.18,
                          "external_factors": 0.1})
        self.assertIsNone(result["calibrated_probability"])
        self.assertFalse(result["ex_final_allowed"])

    def test_four_complete_markets_still_block_pup(self):
        result = assess_markets({market: features() for market in MARKETS},
                                as_of="2026-11-22")
        self.assertTrue(result["evidence_complete"])
        self.assertFalse(result["pup_allowed"])
        self.assertFalse(result["ex_final_allowed"])
        self.assertEqual(set(result["markets"]), set(MARKETS))

    def test_one_market_missing_does_not_borrow_another_markets_evidence(self):
        market_inputs = {market: features() for market in MARKETS}
        del market_inputs["KG_VAR"]
        result = assess_markets(market_inputs, as_of="2026-11-22")
        self.assertFalse(result["evidence_complete"])
        self.assertEqual(result["markets"]["KG_VAR"]["status"], "BLOCKED")
        self.assertFalse(result["pup_allowed"])
        self.assertFalse(result["ex_final_allowed"])

    def test_future_feature_blocks_only_its_market(self):
        market_inputs = {market: features() for market in MARKETS}
        market_inputs["MS2"]["external_factors"]["timestamp"] = "2026-11-22T10:00:00Z"
        result = assess_markets(market_inputs, as_of="2026-11-22")
        self.assertEqual(result["markets"]["MS2"]["status"], "BLOCKED")
        self.assertIn("external_factors:future_evidence",
                      result["markets"]["MS2"]["issues"])
        self.assertEqual(result["markets"]["MS1"]["status"],
                         "EVIDENCE_COMPLETE_UNCALIBRATED")
        self.assertFalse(result["ex_final_allowed"])

    def test_invalid_feature_scores_cannot_generate_a_probability(self):
        for score in (True, -0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(score=score):
                item = features()
                item["team_strength"]["score"] = score
                result = weighted_evidence(item, as_of="2026-11-22")
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIsNone(result["weighted_score"])
                self.assertIsNone(result["calibrated_probability"])
                self.assertFalse(result["ex_final_allowed"])


if __name__ == "__main__":
    unittest.main()
