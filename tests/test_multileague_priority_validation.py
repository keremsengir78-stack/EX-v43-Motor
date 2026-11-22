import unittest
from ex_multileague_priority_validation import validate

class PriorityValidationTests(unittest.TestCase):
    def setUp(self):
        self.plan={"ex_final_allowed":False,"aliases_approved":False,
            "independently_verified_added":0,"total_unmatched":2,
            "priority_buckets":[{"league":"en.1","reason":"SECONDARY_SAME_DAY_SHARED_TEAM",
                                 "count":2,"priority_score":6,"auto_approved":False}]}
        self.diag={"ex_final_allowed":False,"score_verified":False,
            "unmatched_total":2,"by_league":{"en.1":{"source_presence":{
                "SECONDARY_SAME_DAY_SHARED_TEAM":2}}}}
        self.shadow={"ex_final_allowed":False,"shadow_unmatched":2}

    def test_validates_counts(self):
        self.assertEqual(validate(self.plan,self.diag,self.shadow)["validated_buckets"],1)

    def test_rejects_bad_priority(self):
        bad={**self.plan,"priority_buckets":[{**self.plan["priority_buckets"][0],"priority_score":4}]}
        with self.assertRaises(ValueError):
            validate(bad,self.diag,self.shadow)

    def test_rejects_incomplete_buckets(self):
        with self.assertRaises(ValueError):
            validate({**self.plan,"priority_buckets":[]},self.diag,self.shadow)

if __name__=="__main__":
    unittest.main()
