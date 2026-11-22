import unittest
from unittest.mock import patch
from ex_multileague_candidate_resolution import candidates

class CandidateResolutionTests(unittest.TestCase):
    def test_same_day_ranked_without_approval(self):
        data={"ex_final_allowed":False,"independently_verified_added":0,
              "batches":[{"fixtures":[{"league":"en.1","season":"2025-26",
              "date":"2025-08-16","home":"Aston Villa FC","away":"Newcastle United FC"}]}]}
        rows=[{"date":"2025-08-16","home":"Aston Villa","away":"Newcastle","home_goals":0,"away_goals":0},
              {"date":"2025-08-17","home":"Aston Villa","away":"Newcastle","home_goals":9,"away_goals":9}]
        with patch("ex_multileague_candidate_resolution.secondary_rows",return_value=(rows,{"provider":"football-data.co.uk","url":"https://example.org"})):
            result=candidates(data)
        self.assertEqual(result["with_candidates"],1)
        self.assertEqual(len(result["records"][0]["candidates"]),1)
        self.assertFalse(result["records"][0]["independent_score_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_rejects_unsafe(self):
        with self.assertRaises(ValueError):
            candidates({"ex_final_allowed":True,"independently_verified_added":0})
if __name__=="__main__":unittest.main()
