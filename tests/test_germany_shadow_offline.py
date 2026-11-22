import json
import unittest
from ex_germany_shadow_offline import analyze


class GermanyShadowOfflineTests(unittest.TestCase):
    def test_unique_candidate_is_not_score_verified(self):
        candidate = {"ex_final_allowed": False, "candidates": [{
            "league": "de.1", "primary_name": "FC Bayern München",
            "secondary_name": "Bayern Munich", "mapping_conflict": False,
            "review_status": "MANUAL_REVIEW_REQUIRED", "auto_approved": False}]}
        rows = [{"league": "de.1", "home": "FC Bayern München",
                 "away": "RB Leipzig", "source_evidence_json": json.dumps({
                     "secondary_shared_team_candidates": [
                         {"home": "Bayern Munich", "away": "RB Leipzig"}]})}]
        report = analyze(rows, candidate)
        self.assertEqual(report["unique_name_only_candidates"], 1)
        self.assertEqual(report["still_unverified"], 1)
        self.assertEqual(report["verified_score_matches_added"], 0)
        self.assertIs(report["ex_final_allowed"], False)


if __name__ == "__main__":
    unittest.main()
