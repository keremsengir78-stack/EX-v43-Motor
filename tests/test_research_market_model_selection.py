import unittest

from research.market_model_selection import market_pick, metric_report


class MarketSelectionTests(unittest.TestCase):
    def test_validation_order_and_incompatible_vector_remain_visible(self):
        ranks = {m: ("a", "b") for m in ("MS1", "KG_VAR", "2.5_UST")}
        ranks["MS2"] = ("b", "a")
        a = {"MS1": .7, "MS2": .2, "KG_VAR": .8, "2.5_UST": .8}
        b = {"MS1": .3, "MS2": .6, "KG_VAR": .6, "2.5_UST": .8}
        result = market_pick({"a": a, "b": b}, ranks)
        self.assertEqual(.6, result["probabilities"]["MS2"])
        self.assertEqual("INFEASIBLE", result["scoreline"]["status"])

    def test_partial_cohort_and_empty_metrics(self):
        self.assertEqual("MISSING_MARKETS", market_pick({"a": {"MS1": .4}}, {"MS1": ("a",)})["scoreline"]["status"])
        self.assertIsNone(metric_report([])["MS2"]["paired_all"]["daily"]["metrics"])
