import unittest
from unittest.mock import patch
from ex_multileague_strict_score_reconcile import reconcile

class StrictScoreReconcileTests(unittest.TestCase):
    def setUp(self):
        self.fixture={"league":"en.1","season":"2025-26","date":"2025-08-16",
                      "home":"Aston Villa FC","away":"Newcastle United FC"}
        self.batches={"ex_final_allowed":False,"batches":[{"fixtures":[self.fixture]}]}
        self.primary=[{"date":"2025-08-16","league":"en.1","season":"2025-26",
                       "home":"Aston Villa FC","away":"Newcastle United FC","hg":0,"ag":0}]
        self.secondary=[{"date":"2025-08-16","league":"en.1",
                         "home":"Aston Villa","away":"Newcastle United","home_goals":0,"away_goals":0}]
        self.meta={"provider":"football-data.co.uk","url":"https://example.org/secondary.csv","sha256":"abc"}

    def test_exact_match_with_equal_scores(self):
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual((result["confirmed"],result["remaining"]),(1,0))
        self.assertFalse(result["ex_final_allowed"])

    def test_conflicting_score_stays_pending(self):
        self.secondary[0]["away_goals"]=1
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],0)
        self.assertEqual(result["reasons"],{"SCORE_CONFLICT":1})

    def test_ambiguous_secondary_stays_pending(self):
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary*2,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],0)
        self.assertEqual(result["reasons"],{"SECONDARY_MISSING_OR_AMBIGUOUS":1})

    def test_source_failure_stays_pending(self):
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=([],{"error":"timeout"})):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["reasons"],{"SECONDARY_SOURCE_ERROR":1})

    def test_wrong_season_cannot_confirm(self):
        self.primary[0]["season"]="2024-25"
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],0)
        self.assertEqual(result["reasons"],{"PRIMARY_MISSING_OR_AMBIGUOUS":1})

    def test_unapproved_batches_fail_closed(self):
        self.batches["ex_final_allowed"]=True
        with self.assertRaises(ValueError):
            reconcile(self.batches,self.primary)

if __name__=="__main__":
    unittest.main()
