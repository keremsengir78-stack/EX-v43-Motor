import unittest
from unittest.mock import patch
from ex_bulk_match_pipeline import run_batch, run_large_batch


def match(i):
    return {"fixture_id": "fixture-%d" % i, "market": "KG_VAR",
            "records": [], "venue": "home", "season": "2026",
            "previous_season": "2025", "feature_scores": {},
            "as_of": "2026-11-23", "source_observations": {}}


class BulkMatchPipelineTests(unittest.TestCase):
    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            run_batch({"matches": []})

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            run_batch({"matches": [match(1), match(1)]})

    def test_max_batch_limit(self):
        with self.assertRaises(ValueError):
            run_batch({"matches": [match(i) for i in range(501)]})

    def test_missing_input_does_not_block_other_matches(self):
        bad = match(1)
        del bad["source_observations"]
        with patch("ex_bulk_match_pipeline.process_match_evidence",
                   return_value={"status": "BLOCKED", "issues": ["sources:missing"]}):
            result = run_batch({"matches": [bad, match(2)]})
        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["blocked"], 2)
        self.assertIn("input", result["blocker_categories"])
        self.assertFalse(result["ex_final_allowed"])

    def test_successful_evidence_never_promoted_to_final(self):
        with patch("ex_bulk_match_pipeline.process_match_evidence",
                   return_value={"status": "EVIDENCE_READY_UNCALIBRATED", "issues": []}):
            result = run_batch({"matches": [match(1), match(2)]})
        self.assertEqual(result["evidence_ready_uncalibrated"], 2)
        self.assertTrue(all(r["calibrated_probability"] is None for r in result["results"]))
        self.assertFalse(result["ex_final_allowed"])


    def test_same_fixture_multiple_markets(self):
        a, b = match(1), match(1)
        b["market"] = "OVER_2_5"
        with patch("ex_bulk_match_pipeline.process_match_evidence",
                   return_value={"status": "BLOCKED", "issues": ["sources:missing"]}):
            result = run_batch({"matches": [a, b]})
        self.assertEqual(result["processed"], 2)

    def test_chunked_501_matches_no_omission(self):
        with patch("ex_bulk_match_pipeline.process_match_evidence",
                   return_value={"status": "BLOCKED", "issues": ["sources:missing"]}):
            result = run_large_batch({"matches": [match(i) for i in range(501)]})
        self.assertEqual(result["processed"], 501)
        self.assertEqual(result["chunk_count"], 2)
        self.assertEqual(result["blocked"], 501)
        self.assertFalse(result["ex_final_allowed"])

    def test_chunk_size_invalid(self):
        with self.assertRaises(ValueError):
            run_large_batch({"matches": [match(1)]}, 0)

    def test_large_batch_duplicate_across_chunks_rejected(self):
        rows = [match(i) for i in range(501)]
        rows[-1] = match(0)
        with self.assertRaises(ValueError):
            run_large_batch({"matches": rows})


    def test_large_batch_unhashable_identity_rejected_cleanly(self):
        for field, value in (("fixture_id", ["fixture-1"]), ("market", {"bad": "market"}),
                             ("fixture_id", None), ("market", " ")):
            with self.subTest(field=field, value=value):
                row = match(1)
                row[field] = value
                with self.assertRaisesRegex(ValueError, "malformed"):
                    run_large_batch({"matches": [row]})

    def test_large_batch_malformed_row_rejected_cleanly(self):
        with self.assertRaisesRegex(ValueError, "malformed"):
            run_large_batch({"matches": [match(1), None]})

    def test_bad_fixture_is_isolated(self):
        with patch("ex_bulk_match_pipeline.process_match_evidence",
                   side_effect=[ValueError("bad"), {"status": "BLOCKED", "issues": ["window:missing"]}]):
            result = run_batch({"matches": [match(1), match(2)]})
        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["blocker_categories"]["pipeline"], 1)
        self.assertEqual(result["blocker_categories"]["window"], 1)


if __name__ == "__main__":
    unittest.main()
