"""Cross-batch audit must detect corruption and never certify scores."""
import unittest
from ex_strict_review_export_audit import audit_review_exports


def fixture(i):
    return {"league": "en.1", "season": "2025-26", "date": "2025-08-16",
            "home": "Home%d" % i, "away": "Away%d" % i,
            "independent_score_verified": False}


def data():
    source = {"total": 2, "confirmed": 2, "remaining": 0,
              "verified": [{"fixture": fixture(i), "score": [i, 0],
                            "secondary_provider": "provider",
                            "secondary_url": "https://example.org/file.csv",
                            "secondary_sha256": "abc"} for i in range(2)]}
    rows = [{"index": i, "league": "en.1", "season": "2025-26",
             "date": "2025-08-16", "home": "Home%d" % i, "away": "Away%d" % i,
             "matched_score": [i, 0], "secondary_provider": "provider",
             "secondary_url": "https://example.org/file.csv",
             "secondary_sha256": "abc",
             "independent_score_verified": False,
             "review_status": "REQUIRES_INDEPENDENT_SCORE_EVIDENCE"}
            for i in range(2)]
    batch = {"source_total": 2, "offset": 0, "exported": 2,
             "truncated": False, "fixtures": rows,
             "independent_score_verified": False, "ex_final_allowed": False}
    return source, [batch]


class ReviewExportAuditTests(unittest.TestCase):
    def test_valid_export_is_not_source_verification(self):
        result = audit_review_exports(*data())
        self.assertEqual(result["status"], "EXPORT_INTEGRITY_PASSED_NOT_SOURCE_VERIFIED")
        self.assertFalse(result["independent_score_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_score_tampering_is_detected(self):
        source, batches = data()
        batches[0]["fixtures"][0]["matched_score"] = [9, 9]
        self.assertIn("fixture:0:source_mismatch", audit_review_exports(source, batches)["issues"])

    def test_missing_record_is_detected(self):
        source, batches = data()
        batches[0]["fixtures"].pop()
        batches[0]["exported"] = 1
        self.assertIn("coverage:missing_records", audit_review_exports(source, batches)["issues"])

    def test_duplicate_index_is_detected(self):
        source, batches = data()
        batches[0]["fixtures"][1]["index"] = 0
        self.assertIn("fixture:0:duplicate_or_out_of_range",
                      audit_review_exports(source, batches)["issues"])

    def test_forged_approval_is_detected(self):
        source, batches = data()
        batches[0]["fixtures"][0]["independent_score_verified"] = True
        self.assertIn("fixture:0:source_mismatch", audit_review_exports(source, batches)["issues"])


if __name__ == "__main__":
    unittest.main()
