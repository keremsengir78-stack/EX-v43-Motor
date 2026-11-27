from itertools import product
import unittest

from ex_research_scorelines import reconcile, research_pup, validation_order


def markets(home, away, btts, over):
    return {"MS1": home, "MS2": away, "KG_VAR": btts, "2.5_UST": over}


class ScorelineAuditTests(unittest.TestCase):
    def test_feasibility_conditions_and_roundtrip(self):
        for values in product((0, .25, .5, .75, 1), repeat=4):
            h, a, b, o = values
            expected = h + a <= 1 and b - o <= 1 - h - a and o - b <= h + a
            result = reconcile(markets(*values))
            self.assertEqual(expected, result["status"] == "FEASIBLE", values)
            if expected:
                self.assertLessEqual(result["max_absolute_error"], 1e-12)
                self.assertFalse(result["point_scores_identified"])

    def test_pass_and_multiple_candidates_keep_production_locked(self):
        p = markets(.15, .2, .76, .79)
        joint = reconcile(p)
        result = research_pup(p, joint, {})
        self.assertEqual("REVIEW_REQUIRED", result["status"])
        self.assertIn("1-1", result["goal_market_comparison"])
        self.assertIn("one_sided_3_plus", result["goal_market_comparison"])
        result = research_pup(p, joint, {"KG_VAR": "PASS_ODDS_1_19_OR_LOWER"})
        self.assertEqual("2.5_UST", result["selection"])
        self.assertFalse(result["ex_final_allowed"])

    def test_validation_order_ignores_test_scores(self):
        entries = {"models": {key: {"markets": {"MS1": {"validation": {"brier": v}, "test": {"brier": t}}}}
                              for key, v, t in (("A", .20, .30), ("B", .30, .20))}}
        self.assertEqual(["A", "B"], validation_order(entries))
