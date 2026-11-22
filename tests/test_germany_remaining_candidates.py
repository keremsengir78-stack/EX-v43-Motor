import unittest
from ex_germany_remaining_candidates import derive


class RemainingCandidatesTests(unittest.TestCase):
    def test_known_opponent_isolates_new_alias(self):
        report={"ex_final_allowed":False,"aliases_approved":False,
                "unmatched_total":2,"fixtures":[
                    {"date":"2026-08-29","home":"1. FSV Mainz 05",
                     "away":"SC Paderborn 07","secondary_shared_team_candidates":[
                         {"home":"Mainz","away":"Paderborn"}]},
                    {"date":"2026-09-05","home":"SC Paderborn 07",
                     "away":"SC Freiburg","secondary_shared_team_candidates":[
                         {"home":"Paderborn","away":"Freiburg"}]}]}
        known={"candidates":[
            {"primary_name":"1. FSV Mainz 05","secondary_name":"Mainz",
             "mapping_conflict":False,"auto_approved":False},
            {"primary_name":"SC Freiburg","secondary_name":"Freiburg",
             "mapping_conflict":False,"auto_approved":False}]}
        result=derive(report,known)
        self.assertEqual(len(result["candidates"]),1)
        self.assertEqual(result["candidates"][0]["primary_name"],"SC Paderborn 07")
        self.assertEqual(result["candidates"][0]["supporting_fixtures"],2)
        self.assertFalse(result["score_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_incomplete_report_fails(self):
        with self.assertRaises(ValueError):
            derive({"ex_final_allowed":False,"aliases_approved":False,
                    "unmatched_total":8,"fixtures":[]},{"candidates":[]})


if __name__=="__main__":
    unittest.main()
