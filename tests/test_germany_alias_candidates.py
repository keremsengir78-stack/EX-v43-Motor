import json
import unittest
from ex_germany_alias_candidates import candidates


class GermanAliasCandidateTests(unittest.TestCase):
    def test_single_matching_opponent_only(self):
        rows = [{"season": "2025-26", "league": "de.1",
                 "date": "2025-08-22", "home": "FC Bayern München",
                 "away": "RB Leipzig",
                 "source_evidence_json": json.dumps({
                     "source_presence_status": "SECONDARY_SAME_DAY_SHARED_TEAM",
                     "secondary_shared_team_candidates": [
                         {"home": "Bayern Munich", "away": "RB Leipzig"}]})}]
        found = candidates(rows)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["primary_name"], "FC Bayern München")
        self.assertEqual(found[0]["secondary_name"], "Bayern Munich")
        self.assertFalse(found[0]["auto_approved"])
        self.assertEqual(found[0]["review_status"], "MANUAL_REVIEW_REQUIRED")

    def test_never_infer_when_both_teams_differ(self):
        rows = [{"season": "2025-26", "league": "de.1",
                 "date": "2025-08-22", "home": "FC Bayern München",
                 "away": "RB Leipzig",
                 "source_evidence_json": json.dumps({
                     "source_presence_status": "SECONDARY_SAME_DAY_SHARED_TEAM",
                     "secondary_shared_team_candidates": [
                         {"home": "Bayern Munich", "away": "Leipzig"}]})}]
        self.assertEqual(candidates(rows), [])

    def test_rejects_broken_evidence(self):
        with self.assertRaises(ValueError):
            candidates([{"league": "de.1", "source_evidence_json": "not json"}])


if __name__ == "__main__":
    unittest.main()
