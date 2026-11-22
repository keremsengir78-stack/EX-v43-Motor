import unittest
from ex_multileague_alias_candidates import extract


class MultileagueCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.report={"ex_final_allowed":False,"unmatched_total":2,
                     "germany_unmatched":0,"groups":[{"league":"en.1",
                     "unmatched_count":2,"unmatched_details":[
                         {"date":"2026-01-02","home":"Manchester United","away":"Chelsea",
                          "source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM",
                          "secondary_shared_team_candidates":[{"home":"Man United","away":"Chelsea"}]},
                         {"date":"2026-01-09","home":"Manchester United","away":"Arsenal",
                          "source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM",
                          "secondary_shared_team_candidates":[{"home":"Man United","away":"Arsenal"}]}]}]}
    def test_two_supporting_matches_do_not_approve(self):
        report=extract(self.report)
        self.assertEqual(report["non_germany_unmatched"],2)
        self.assertEqual(report["candidate_count"],1)
        self.assertEqual(report["candidates"][0]["supporting_fixtures"],2)
        self.assertFalse(report["score_verified"])
        self.assertFalse(report["ex_final_allowed"])

    def test_rejects_missing_rows(self):
        with self.assertRaises(ValueError):
            extract({**self.report,"groups":[{**self.report["groups"][0],
                    "unmatched_count":3}]})


if __name__=="__main__":
    unittest.main()
