import unittest
from ex_live_bridge_delta import compare_audits


def audit(matched, unmatched, conflicts=0, league="en.1"):
    return {"as_of": "2026-11-22", "cases": [{
        "league": league, "season": "2026-2027", "day": "2026-10-25",
        "as_of": "2026-11-22", "matched": matched, "unmatched": unmatched,
        "conflict_count": conflicts, "unmatched_details": [],
        "alias_suggestions": []}]}


class DeltaAuditTests(unittest.TestCase):
    def test_gain_does_not_unlock_final(self):
        result = compare_audits(audit(1, 4), audit(4, 1))
        self.assertEqual(result["matched_delta"], 3)
        self.assertEqual(result["reviewed_unmatched"], 1)
        self.assertEqual(result["regression_count"], 0)
        self.assertFalse(result["ex_final_allowed"])
        self.assertFalse(result["calibration_certified"])

    def test_matching_regression_is_reported(self):
        result = compare_audits(audit(4, 1), audit(3, 2))
        self.assertEqual(result["status"], "REGRESSION_DETECTED")
        self.assertEqual(result["regression_count"], 1)

    def test_new_score_conflict_is_regression(self):
        result = compare_audits(audit(2, 1), audit(2, 1, conflicts=1))
        self.assertEqual(result["regression_count"], 1)

    def test_mismatched_cutoff_rejected(self):
        reviewed = audit(3, 2)
        reviewed["as_of"] = "2026-11-23"
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 3), reviewed)

    def test_mismatched_fixture_rejected(self):
        reviewed = audit(3, 2, league="it.1")
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 3), reviewed)

    def test_empty_audits_rejected(self):
        with self.assertRaises(ValueError):
            compare_audits({"as_of": "2026-11-22", "cases": []},
                           {"as_of": "2026-11-22", "cases": []})


if __name__ == "__main__":
    unittest.main()
