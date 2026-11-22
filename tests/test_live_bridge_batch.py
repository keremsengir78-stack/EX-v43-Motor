import unittest
from unittest.mock import patch

import ex_live_bridge_batch as batch


def report(status="PROVISIONAL_MATCH_UNAUDITED", matched=2, unmatched=0, ambiguous=0, conflicts=0):
    return {"status": status, "matched": matched, "unmatched": unmatched,
            "ambiguous": ambiguous, "conflict_count": conflicts,
            "ex_final_allowed": False}


class MultiCaseAuditTests(unittest.TestCase):
    def test_twenty_case_aggregate(self):
        with patch.object(batch, "run_pilot", return_value=report()) as fetch:
            result = batch.run_batch("2026-11-22")
        self.assertEqual(fetch.call_count, len(batch.DEFAULT_CASES))
        self.assertEqual(result["matched"], 2 * len(batch.DEFAULT_CASES))
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["status"], "PROVISIONAL_MULTI_CASE")
        self.assertFalse(result["ex_final_allowed"])
        self.assertFalse(result["calibration_certified"])

    def test_blocked_case_keeps_batch_incomplete(self):
        with patch.object(batch, "run_pilot", side_effect=[report(), report("BLOCKED", 0)]):
            result = batch.run_batch("2026-11-22", batch.DEFAULT_CASES[:2])
        self.assertEqual(result["blocked_cases"], 1)
        self.assertEqual(result["status"], "INCOMPLETE_OR_CONFLICTING")

    def test_conflict_keeps_batch_incomplete(self):
        with patch.object(batch, "run_pilot", return_value=report("SCORE_CONFLICT", 0, 1, 0, 1)):
            result = batch.run_batch("2026-11-22", batch.DEFAULT_CASES[:1])
        self.assertEqual(result["conflict_count"], 1)
        self.assertEqual(result["status"], "INCOMPLETE_OR_CONFLICTING")

    def test_partial_case_is_counted(self):
        with patch.object(batch, "run_pilot", return_value=report("PARTIAL_PROVISIONAL_MATCH", 1, 2)):
            result = batch.run_batch("2026-11-22", batch.DEFAULT_CASES[:1])
        self.assertEqual(result["partial_cases"], 1)
        self.assertEqual(result["blocked_cases"], 0)
        self.assertFalse(result["ex_final_allowed"])

    def test_reviewed_aliases_are_opt_in_and_scoped(self):
        with patch.object(batch, "run_pilot", return_value=report()) as fetch:
            result = batch.run_batch("2026-11-22", batch.DEFAULT_CASES, reviewed_aliases=True)
        self.assertTrue(result["reviewed_aliases_enabled"])
        self.assertEqual(fetch.call_count, 5)
        self.assertEqual(fetch.call_args.kwargs["alias"], batch.REVIEWED_ALIASES)
        for call in fetch.call_args_list:
            league = call.args[0]
            self.assertEqual("alias" in call.kwargs, league in batch.REVIEWED_ALIASES)
        self.assertFalse(result["ex_final_allowed"])

    def test_empty_batch_not_success(self):
        result = batch.run_batch("2026-11-22", ())
        self.assertEqual(result["status"], "INCOMPLETE_OR_CONFLICTING")
        self.assertEqual(result["coverage"], 0.0)

    def test_partial_data_does_not_certify_sample(self):
        with patch.object(batch, "run_pilot", return_value=report("PARTIAL_PROVISIONAL_MATCH", 1, 2)):
            result = batch.run_batch("2026-11-22", batch.DEFAULT_CASES[:1])
        self.assertAlmostEqual(result["coverage"], 1 / 3)
        self.assertFalse(result["sample_sufficiency_certified"])


if __name__ == "__main__":
    unittest.main()
