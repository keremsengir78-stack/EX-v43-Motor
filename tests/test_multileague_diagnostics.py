import unittest
from ex_multileague_diagnostics import diagnose


class MultiLeagueDiagnosticsTests(unittest.TestCase):
    def test_counts_all_rows_and_preserves_lock(self):
        report={"ex_final_allowed":False,"unmatched_total":3,
                "germany_unmatched":1,"groups":[
                    {"league":"de.1","unmatched_count":1,"unmatched_details":[{}]},
                    {"league":"en.1","unmatched_count":2,"unmatched_details":[
                        {"date":"2026-01-01","home":"A","away":"B",
                         "source_presence_status":"SECONDARY_DATE_PRESENT_NO_TEAM_MATCH"},
                        {"date":"2026-01-02","home":"C","away":"D",
                         "source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM"}]}]}
        result=diagnose(report)
        self.assertEqual(result["unmatched_total"],2)
        self.assertEqual(result["by_league"]["en.1"]["count"],2)
        self.assertFalse(result["score_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_rejects_truncated_group(self):
        with self.assertRaises(ValueError):
            diagnose({"ex_final_allowed":False,"unmatched_total":2,
                      "germany_unmatched":0,"groups":[{"league":"fr.1",
                      "unmatched_count":2,"unmatched_details":[{}]}]})


if __name__=="__main__":
    unittest.main()
