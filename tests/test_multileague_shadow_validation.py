import unittest
from ex_multileague_shadow_validation import validate


class MultiLeagueShadowValidationTests(unittest.TestCase):
    def setUp(self):
        self.comparison={"ex_final_allowed":False,"aliases_approved":False,
            "comparison_only":True,"independently_verified_added":0,
            "baseline_unmatched":4,"shadow_unmatched":3,
            "shadow_unmatched_by_league":{"en.1":1,"es.1":1,"it.1":1,"fr.1":0},
            "score_conflicts":0,"source_errors":[]}
        self.diagnostics={"ex_final_allowed":False,"score_verified":False,
            "unmatched_total":3,"by_league":{
                "en.1":{"count":1},"es.1":{"count":1},
                "it.1":{"count":1}}}

    def test_safe_comparison(self):
        self.assertEqual(validate(self.comparison,self.diagnostics)["name_only_reduction"],1)

    def test_rejects_missing_league(self):
        bad={**self.comparison,"shadow_unmatched_by_league":{"en.1":3}}
        with self.assertRaises(ValueError):
            validate(bad,self.diagnostics)

    def test_rejects_false_score_confirmation(self):
        with self.assertRaises(ValueError):
            validate({**self.comparison,"independently_verified_added":1},self.diagnostics)


if __name__=="__main__":
    unittest.main()
