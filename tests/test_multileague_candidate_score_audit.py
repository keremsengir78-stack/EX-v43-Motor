import unittest
from ex_multileague_candidate_score_audit import audit

class CandidateScoreAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture={"league":"es.1","season":"2025-26","date":"2025-08-23","home":"Levante UD","away":"FC Barcelona"}
        self.report={"ex_final_allowed":False,"independently_verified_added":0,"unique_name_candidates":1,
            "records":[{"fixture":self.fixture,"candidate":{"home":"Levante","away":"Barcelona","home_goals":2,"away_goals":3}}]}
        self.primary=[{"league":"es.1","season":"2025-26","date":"2025-08-23","home":"Levante UD","away":"FC Barcelona","hg":2,"ag":3}]

    def test_agreement_is_not_identity_verification(self):
        result=audit(self.report,self.primary)
        self.assertEqual(result["counts"],{"SCORE_AGREES_IDENTITY_UNREVIEWED":1})
        self.assertEqual(result["independently_verified_added"],0)
        self.assertFalse(result["records"][0]["independent_score_verified"])

    def test_score_conflict_is_not_approved(self):
        self.report["records"][0]["candidate"]["away_goals"]=4
        self.assertEqual(audit(self.report,self.primary)["counts"],{"SCORE_CONFLICT":1})

    def test_season_mismatch_is_not_approved(self):
        self.primary[0]["season"]="2024-25"
        self.assertEqual(audit(self.report,self.primary)["counts"],{"PRIMARY_MISSING_OR_AMBIGUOUS":1})

    def test_rejects_truncated_candidate_report(self):
        self.report["unique_name_candidates"]=2
        with self.assertRaises(ValueError):audit(self.report,self.primary)

if __name__=="__main__":
    unittest.main()
