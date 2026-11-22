import unittest
from ex_multileague_review_batches import build
from ex_multileague_batch_validation import validate

class BatchValidationTests(unittest.TestCase):
    def setUp(self):
        self.summary={"ex_final_allowed":False,"unmatched_total":2,
            "groups":[{"league":"en.1","season":"2025-26","unmatched_count":2,
                "unmatched_details":[{"date":"2025-08-01","home":"A","away":"B",
                    "source_presence_status":"SECONDARY_DATE_PRESENT_NO_TEAM_MATCH"},
                    {"date":"2025-08-02","home":"C","away":"D",
                    "source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM"}]}]}

    def test_lossless_validation(self):
        self.assertEqual(validate(build(self.summary,1),self.summary)["fixtures_checked"],2)

    def test_rejects_duplicate_across_batches(self):
        batches=build(self.summary,1)
        batches["batches"][1]["fixtures"][0]=batches["batches"][0]["fixtures"][0]
        with self.assertRaises(ValueError):
            validate(batches,self.summary)

    def test_rejects_unapproved_verification(self):
        batches=build(self.summary,1)
        batches["batches"][0]["fixtures"][0]["independent_score_verified"]=True
        with self.assertRaises(ValueError):
            validate(batches,self.summary)

if __name__=="__main__":
    unittest.main()
