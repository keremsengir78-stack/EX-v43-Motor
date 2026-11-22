import unittest
from ex_live_bridge_delta import compare_audits


def audit(matched, unmatched, conflicts=0, league="en.1", reviewed=False):
    return {"as_of": "2026-11-22", "reviewed_aliases_enabled": reviewed,
            "ex_final_allowed": False, "independent_sources_confirmed": False,
            "calibration_certified": False, "cases": [{
        "league": league, "season": "2026-2027", "day": "2026-10-25",
        "as_of": "2026-11-22", "matched": matched, "unmatched": unmatched,
        "ex_final_allowed": False,
        "conflict_count": conflicts,
        "status": "SCORE_CONFLICT" if conflicts else ("PARTIAL_PROVISIONAL_MATCH" if unmatched else "PROVISIONAL_MATCH_UNAUDITED"),
        "unmatched_details": [],
        "alias_suggestions": []}]}


class DeltaAuditTests(unittest.TestCase):
    def test_gain_does_not_unlock_final(self):
        result = compare_audits(audit(1, 4), audit(4, 1, reviewed=True))
        self.assertEqual(result["matched_delta"], 3)
        self.assertEqual(result["reviewed_unmatched"], 1)
        self.assertEqual(result["regression_count"], 0)
        self.assertEqual(result["technical_gate"], "PASSED_AUDIT_COMPARISON")
        self.assertEqual(result["data_gate"], "BLOCKED_UNRESOLVED_FIXTURES")
        self.assertFalse(result["ex_final_allowed"])
        self.assertFalse(result["calibration_certified"])

    def test_matching_regression_is_reported(self):
        result = compare_audits(audit(4, 1), audit(3, 2, reviewed=True))
        self.assertEqual(result["status"], "REGRESSION_DETECTED")
        self.assertEqual(result["regression_count"], 1)
        self.assertEqual(result["technical_gate"], "FAILED_REGRESSION")

    def test_new_score_conflict_is_regression(self):
        result = compare_audits(audit(2, 1), audit(2, 1, conflicts=1, reviewed=True))
        self.assertEqual(result["regression_count"], 1)

    def test_mismatched_cutoff_rejected(self):
        reviewed = audit(3, 2, reviewed=True)
        reviewed["as_of"] = "2026-11-23"
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 3), reviewed)

    def test_mismatched_fixture_rejected(self):
        reviewed = audit(3, 2, league="it.1", reviewed=True)
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 3), reviewed)

    def test_reversed_audit_modes_rejected(self):
        raw = audit(2, 3)
        raw["reviewed_aliases_enabled"] = True
        with self.assertRaises(ValueError):
            compare_audits(raw, audit(3, 2, reviewed=True))

    def test_fixture_population_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 3), audit(3, 3, reviewed=True))

    def test_duplicate_case_rejected(self):
        raw = audit(2, 3)
        reviewed = audit(3, 2, reviewed=True)
        raw["cases"] *= 2
        reviewed["cases"] *= 2
        with self.assertRaises(ValueError):
            compare_audits(raw, reviewed)

    def test_invalid_counts_rejected(self):
        reviewed = audit(3, 2, reviewed=True)
        reviewed["cases"][0]["matched"] = -1
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 3), reviewed)

    def test_remaining_by_league_reported(self):
        result = compare_audits(audit(2, 3), audit(3, 2, reviewed=True))
        self.assertEqual(result["remaining_by_league"], {"en.1": 2})
        self.assertEqual(result["cases_with_unresolved"], 1)
        self.assertEqual(result["review_queue"][0]["league"], "en.1")
        self.assertEqual(result["review_queue"][0]["unmatched"], 2)
        self.assertEqual(result["cases"][0]["unresolved_reason"], "NAME_OR_FIXTURE_MISMATCH_REQUIRES_SOURCE_REVIEW")

    def test_unverified_independence_claim_rejected(self):
        reviewed = audit(3, 2, reviewed=True)
        reviewed["independent_sources_confirmed"] = True
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 3), reviewed)

    def test_case_level_final_certification_rejected(self):
        reviewed = audit(3, 2, reviewed=True)
        reviewed["cases"][0]["ex_final_allowed"] = True
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 3), reviewed)

    def test_missing_raw_mode_rejected(self):
        raw = audit(2, 3)
        del raw["reviewed_aliases_enabled"]
        with self.assertRaises(ValueError):
            compare_audits(raw, audit(3, 2, reviewed=True))

    def test_unexpected_final_certification_rejected(self):
        reviewed = audit(3, 2, reviewed=True)
        reviewed["ex_final_allowed"] = True
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 3), reviewed)

    def test_hidden_conflict_status_rejected(self):
        reviewed = audit(2, 1, conflicts=1, reviewed=True)
        reviewed["cases"][0]["status"] = "PARTIAL_PROVISIONAL_MATCH"
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 1), reviewed)

    def test_false_complete_status_rejected(self):
        reviewed = audit(3, 2, reviewed=True)
        reviewed["cases"][0]["status"] = "PROVISIONAL_MATCH_UNAUDITED"
        with self.assertRaises(ValueError):
            compare_audits(audit(2, 3), reviewed)

    def test_review_queue_counts_actual_mismatch_reasons(self):
        reviewed = audit(3, 2, reviewed=True)
        reviewed["cases"][0]["unmatched_details"] = [
            {"reason": "not_found"}, {"reason": "not_found"}]
        result = compare_audits(audit(2, 3), reviewed)
        self.assertEqual(result["review_queue"][0]["reason_counts"], {"not_found": 2})

    def test_empty_audits_rejected(self):
        with self.assertRaises(ValueError):
            compare_audits({"as_of": "2026-11-22", "cases": []},
                           {"as_of": "2026-11-22", "cases": []})


if __name__ == "__main__":
    unittest.main()
