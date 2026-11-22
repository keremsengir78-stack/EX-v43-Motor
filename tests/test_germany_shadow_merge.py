import unittest
from ex_germany_shadow_merge import merge_candidates


def candidate(p,s):
    return {"league":"de.1","primary_name":p,"secondary_name":s,
            "mapping_conflict":False,"review_status":"MANUAL_REVIEW_REQUIRED",
            "auto_approved":False}


class ShadowMergeTests(unittest.TestCase):
    def test_combines_without_approval(self):
        result=merge_candidates(
            {"ex_final_allowed":False,"candidates":[candidate("Mainz","Mainz 05")]},
            {"ex_final_allowed":False,"score_verified":False,"aliases_approved":False,
             "candidates":[candidate("Elversberg","SV Elversberg")]})
        self.assertEqual(len(result["candidates"]),2)
        self.assertFalse(result["score_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_rejects_conflicting_mapping(self):
        with self.assertRaises(ValueError):
            merge_candidates(
                {"ex_final_allowed":False,"candidates":[candidate("Team A","Shared")]},
                {"ex_final_allowed":False,"score_verified":False,"aliases_approved":False,
                 "candidates":[candidate("Team B","Shared")]})


if __name__=="__main__":
    unittest.main()
