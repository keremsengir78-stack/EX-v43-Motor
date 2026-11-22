import unittest
from ex_multileague_candidate_summary import summarize

class CandidateSummaryTests(unittest.TestCase):
    def test_counts_source_coverage(self):
        report={"total_fixtures":2,"ex_final_allowed":False,"records":[
            {"fixture":{"league":"en.1"},"candidates":[{"name_similarity":.96,"home_similarity":.94,"away_similarity":.98}],"independent_score_verified":False},
            {"fixture":{"league":"it.1"},"candidates":[],"source_error":"missing","independent_score_verified":False}]}
        result=summarize(report)
        self.assertEqual(result["with_candidates"],1)
        self.assertEqual(result["high_name_similarity_candidates"],1)
        self.assertEqual(result["by_league"]["it.1"]["source_errors"],1)
        self.assertEqual(result["independently_verified_added"],0)

    def test_rejects_false_approval(self):
        report={"total_fixtures":1,"ex_final_allowed":False,"records":[
            {"fixture":{"league":"en.1"},"candidates":[],"independent_score_verified":True}]}
        with self.assertRaises(ValueError):summarize(report)
if __name__=="__main__":unittest.main()
