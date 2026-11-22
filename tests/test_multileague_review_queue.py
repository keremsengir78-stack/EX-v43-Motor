import unittest
from ex_multileague_review_queue import build


class MultiLeagueQueueTests(unittest.TestCase):
    def test_priority_and_truncation(self):
        summary={"ex_final_allowed":False,"unmatched_total":3,"germany_unmatched":0,
                 "groups":[{"league":"en.1","season":"2026-27","unmatched_count":3,
                            "unmatched_details":[
                                {"date":"2026-01-01","home":"A","away":"B",
                                 "source_presence_status":"SECONDARY_DATE_EMPTY"},
                                {"date":"2026-01-02","home":"C","away":"D",
                                 "source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM"},
                                {"date":"2026-01-03","home":"E","away":"F",
                                 "source_presence_status":"SECONDARY_DATE_PRESENT_NO_TEAM_MATCH"}]}]}
        result=build(summary,2)
        self.assertEqual(result["total_review_queue"],3)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["fixtures"][0]["home"],"C")
        self.assertEqual(result["fixtures"][1]["home"],"E")
        self.assertFalse(result["score_verified"])

    def test_rejects_missing_rows(self):
        with self.assertRaises(ValueError):
            build({"ex_final_allowed":False,"unmatched_total":2,
                   "germany_unmatched":0,"groups":[{"league":"fr.1",
                   "season":"2026-27","unmatched_count":2,
                   "unmatched_details":[{}]}]})


if __name__=="__main__":
    unittest.main()
