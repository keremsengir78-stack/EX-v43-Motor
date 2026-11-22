import unittest
from ex_germany_expanded_validation import validate


def candidate(p,s):
    return {"primary_name":p,"secondary_name":s,
            "mapping_conflict":False,"auto_approved":False}


class ExpandedValidationTests(unittest.TestCase):
    def setUp(self):
        self.base={"germany_unmatched":339}
        self.first={"shadow_germany_unmatched":8,"ex_final_allowed":False}
        self.expanded={"expanded_shadow_unmatched":0,
                       "expanded_shadow_score_conflicts":0,
                       "expanded_shadow_source_errors":[],
                       "candidate_count":2,"comparison_only":True,
                       "aliases_approved":False,
                       "independently_verified_added":0,"ex_final_allowed":False}
        self.candidates=[{"ex_final_allowed":False,"candidates":[candidate("A","B")]},
                         {"ex_final_allowed":False,"candidates":[candidate("C","D")]}]

    def test_zero_unmatched_is_not_approval(self):
        result=validate(self.base,self.first,self.expanded,self.candidates)
        self.assertEqual(result["shadow_name_reduction"],339)
        self.assertEqual(result["independently_verified_added"],0)
        self.assertFalse(result["ex_final_allowed"])

    def test_rejects_fake_score_verification(self):
        with self.assertRaises(ValueError):
            validate(self.base,self.first,{**self.expanded,
                "independently_verified_added":339},self.candidates)

    def test_rejects_conflicts(self):
        with self.assertRaises(ValueError):
            validate(self.base,self.first,{**self.expanded,
                "expanded_shadow_score_conflicts":1},self.candidates)

    def test_rejects_duplicate_candidates(self):
        with self.assertRaises(ValueError):
            validate(self.base,self.first,self.expanded,
                     [self.candidates[0],self.candidates[0]])


if __name__=="__main__":
    unittest.main()
