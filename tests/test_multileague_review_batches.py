import unittest
from ex_multileague_review_batches import build

class ReviewBatchTests(unittest.TestCase):
    def setUp(self):
        self.summary={"ex_final_allowed":False,"unmatched_total":2,
            "groups":[{"league":"en.1","season":"2025-26","unmatched_count":2,
                "unmatched_details":[{"date":"2025-08-01","home":"A","away":"B",
                    "source_presence_status":"SECONDARY_DATE_PRESENT_NO_TEAM_MATCH"},
                    {"date":"2025-08-02","home":"C","away":"D",
                    "source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM"}]}]}

    def test_lossless_batches(self):
        result=build(self.summary,1)
        self.assertEqual(result["batch_count"],2)
        self.assertEqual(result["batches"][0]["fixtures"][0]["home"],"C")
        self.assertFalse(result["ex_final_allowed"])

    def test_rejects_duplicate_fixture(self):
        fixture=self.summary["groups"][0]["unmatched_details"][0]
        self.summary["groups"][0]["unmatched_details"][1]=fixture
        with self.assertRaises(ValueError):
            build(self.summary)

    def test_rejects_truncation(self):
        self.summary["groups"][0]["unmatched_details"].pop()
        with self.assertRaises(ValueError):
            build(self.summary)

if __name__=="__main__":
    unittest.main()
