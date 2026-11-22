import unittest
from ex_multileague_priority_plan import plan

class PriorityPlanTests(unittest.TestCase):
    def test_prioritizes_supported_source_evidence(self):
        report={"ex_final_allowed":False,"unmatched_total":2,"germany_unmatched":0,
                "groups":[{"league":"en.1","season":"2025-26","unmatched_count":2,
                           "unmatched_details":[
                               {"date":"2025-08-01","home":"A","away":"B","source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM"},
                               {"date":"2025-08-02","home":"C","away":"D","source_presence_status":"SECONDARY_DATE_PRESENT_NO_TEAM_MATCH"}]}]}
        result=plan(report)
        self.assertEqual(result["total_unmatched"],2)
        self.assertEqual(result["priority_buckets"][0]["priority_score"],3)
        self.assertFalse(result["ex_final_allowed"])

    def test_rejects_unknown_source_status(self):
        with self.assertRaises(ValueError):
            plan({"ex_final_allowed":False,"unmatched_total":1,"germany_unmatched":0,
                  "groups":[{"league":"it.1","season":"2025-26","unmatched_count":1,
                             "unmatched_details":[{"source_presence_status":"UNKNOWN"}]}]})

if __name__=="__main__":
    unittest.main()
