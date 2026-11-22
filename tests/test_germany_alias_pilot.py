import unittest
from ex_germany_alias_pilot import build_pilot


class GermanyAliasPilotTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "league": "de.1", "primary_name": "FC Bayern München",
            "secondary_name": "Bayern Munich", "mapping_conflict": False,
            "review_status": "MANUAL_REVIEW_REQUIRED", "auto_approved": False}

    def test_quarantined_candidate_map(self):
        result = build_pilot({"ex_final_allowed": False, "candidates": [self.candidate]})
        self.assertEqual(result, {"de.1": {"Bayern Munich": "FC Bayern München"}})

    def test_rejects_approval_conflicts_and_unlocked_final(self):
        for changed in ({"mapping_conflict": True}, {"auto_approved": True},
                        {"review_status": "APPROVED"}, {"secondary_name": ""}):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    build_pilot({"ex_final_allowed": False,
                                 "candidates": [{**self.candidate, **changed}]})
        with self.assertRaises(ValueError):
            build_pilot({"ex_final_allowed": True, "candidates": [self.candidate]})

    def test_rejects_two_primaries_for_same_secondary(self):
        with self.assertRaises(ValueError):
            build_pilot({"ex_final_allowed": False, "candidates": [
                self.candidate, {**self.candidate, "primary_name": "Different"}]})


if __name__ == "__main__":
    unittest.main()
