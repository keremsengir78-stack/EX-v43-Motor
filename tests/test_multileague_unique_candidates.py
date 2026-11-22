import unittest
from ex_multileague_unique_candidates import select

class UniqueCandidatesTests(unittest.TestCase):
    def record(self,home="A"):
        return {"fixture":{"league":"en.1","season":"2025-26","date":"2025-08-16","home":home,"away":"B"},
                "candidates":[{"home":"A","away":"B","home_goals":1,"away_goals":0,
                    "name_similarity":.97,"home_similarity":.98,"away_similarity":.96}],
                "source_provider":"football-data.co.uk","independent_score_verified":False}
    def test_unique(self):
        result=select({"total_fixtures":1,"records":[self.record()],"ex_final_allowed":False,"independently_verified_added":0})
        self.assertEqual(result["unique_name_candidates"],1)
        self.assertFalse(result["records"][0]["independent_score_verified"])
    def test_conflicting_claims(self):
        result=select({"total_fixtures":2,"records":[self.record(),self.record("C")],
                       "ex_final_allowed":False,"independently_verified_added":0})
        self.assertEqual(result["unique_name_candidates"],0)
    def test_rejects_truncated(self):
        with self.assertRaises(ValueError):
            select({"total_fixtures":1,"records":[],"ex_final_allowed":False,"independently_verified_added":0})
if __name__=="__main__":unittest.main()
