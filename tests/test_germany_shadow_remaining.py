import unittest
from ex_germany_shadow_remaining import extract


class ShadowRemainingTests(unittest.TestCase):
    def test_exact_eight_remain_unverified(self):
        audit = {
            "secondary_unverified": 8,
            "secondary_unmatched_by_season": {"2025-26/de.1": 5, "2026-27/de.1": 3},
            "secondary_review_queue": [
                {"season": "2025-26", "league": "de.1",
                 "unmatched": [{"date": f"2025-09-{i:02d}", "reason": "not_found"} for i in range(1, 6)]},
                {"season": "2026-27", "league": "de.1",
                 "unmatched": [{"date": f"2026-09-{i:02d}", "reason": "not_found"} for i in range(1, 4)]}]}
        report = extract(audit)
        self.assertEqual(len(report["fixtures"]), 8)
        self.assertFalse(report["ex_final_allowed"])
        self.assertFalse(report["aliases_approved"])

    def test_rejects_missing_evidence(self):
        with self.assertRaises(ValueError):
            extract({"secondary_unverified": 8,
                     "secondary_unmatched_by_season": {"2025-26/de.1": 8},
                     "secondary_review_queue": []})


if __name__ == "__main__":
    unittest.main()
