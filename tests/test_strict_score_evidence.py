"""Strict matching cannot silently become independent score verification."""
import unittest

from ex_strict_score_evidence import verify_strict_report


def report(verified=False):
    return {"total": 1, "confirmed": 1, "remaining": 0,
            "verified": [{
                "fixture": {"independent_score_verified": verified},
                "verification": "EXACT_TEAM_DATE_SCORE_MATCH",
                "secondary_provider": "fixture-provider",
                "secondary_url": "https://example.org/scores.csv",
            }]}


class StrictScoreEvidenceTests(unittest.TestCase):
    def test_matched_but_not_independently_verified_is_blocked(self):
        result = verify_strict_report(report())
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("fixture:0:independent_source_unverified", result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_verified_field_is_not_external_certification(self):
        result = verify_strict_report(report(True))
        self.assertEqual(result["status"], "EVIDENCE_FIELDS_PRESENT_NOT_CERTIFIED")
        self.assertFalse(result["independent_score_verified"])
        self.assertFalse(result["ex_final_allowed"])


    def test_malformed_https_url_does_not_count_as_provenance(self):
        for url in ("https://", "https:///missing-host", "https://user:pass@example.org/x",
                    "https://example.org/x#fragment", "https://example.org:9999/x"):
            with self.subTest(url=url):
                item = report(True)
                item["verified"][0]["secondary_url"] = url
                result = verify_strict_report(item)
                self.assertIn("fixture:0:source_provenance_missing", result["issues"])

    def test_duplicate_fixture_cannot_inflate_confirmed_count(self):
        item = report(True)
        fixture = item["verified"][0]["fixture"]
        fixture.update({"fixture_id": "game-1", "home_team": "Home",
                        "away_team": "Away", "kickoff_at": "2026-01-01T12:00:00Z"})
        item["verified"].append(dict(item["verified"][0]))
        item["total"] = 2
        item["confirmed"] = 2
        result = verify_strict_report(item)
        self.assertIn("fixture:1:duplicate", result["issues"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_counts_must_balance(self):
        item = report()
        item["remaining"] = 1
        result = verify_strict_report(item)
        self.assertIn("counts:sum_mismatch", result["issues"])

    def test_boolean_count_is_invalid(self):
        item = report()
        item["confirmed"] = True
        result = verify_strict_report(item)
        self.assertIn("counts:invalid", result["issues"])

    def test_missing_source_provenance_is_blocked(self):
        item = report(True)
        item["verified"][0]["secondary_url"] = ""
        result = verify_strict_report(item)
        self.assertIn("fixture:0:source_provenance_missing", result["issues"])


if __name__ == "__main__":
    unittest.main()
