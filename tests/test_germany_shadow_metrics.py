import unittest
from ex_germany_shadow_metrics import validate_shadow_metrics


class ShadowMetricsTests(unittest.TestCase):
    def setUp(self):
        self.base = {"germany_unmatched": 339}
        self.shadow = {"shadow_germany_unmatched": 8,
                       "shadow_score_conflicts": 0,
                       "shadow_source_errors": [],
                       "aliases_approved": False, "ex_final_allowed": False}
        self.offline = {"germany_unmatched_baseline": 339,
                        "unique_name_only_candidates": 36,
                        "verified_score_matches_added": 0,
                        "aliases_approved": False, "ex_final_allowed": False}

    def test_shadow_reduction_not_independent_verification(self):
        result = validate_shadow_metrics(self.base, self.shadow, self.offline)
        self.assertEqual(result["shadow_reduction"], 331)
        self.assertEqual(result["independently_verified_added"], 0)
        self.assertIs(result["ex_final_allowed"], False)

    def test_rejects_bad_baseline(self):
        with self.assertRaises(ValueError):
            validate_shadow_metrics(self.base, self.shadow,
                                    {**self.offline, "germany_unmatched_baseline": 338})

    def test_rejects_unapproved_source_errors(self):
        with self.assertRaises(ValueError):
            validate_shadow_metrics(self.base,
                                    {**self.shadow, "shadow_source_errors": ["network failure"]},
                                    self.offline)

    def test_rejects_false_approval(self):
        with self.assertRaises(ValueError):
            validate_shadow_metrics(self.base,
                                    {**self.shadow, "aliases_approved": True},
                                    self.offline)


if __name__ == "__main__":
    unittest.main()
