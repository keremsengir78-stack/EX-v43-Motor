import unittest
from ex_source_agreement import verify_fixture_sources


def fixture(source):
    return {"source_id": source, "verified": True, "fixture_id": "match-1",
            "home_team": "Home", "away_team": "Away",
            "kickoff_at": "2026-01-01T12:00:00Z", "home_goals": 2, "away_goals": 1}


class SourceAgreementTests(unittest.TestCase):
    def test_two_matching_sources(self):
        result = verify_fixture_sources([fixture("provider-A"), fixture("provider-B")],
                                        "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "CROSS_VERIFIED_INPUT")
        self.assertEqual(result["independent_sources_confirmed"], 2)
        self.assertFalse(result["ex_final_allowed"])

    def test_duplicate_source_is_blocked(self):
        result = verify_fixture_sources([fixture("provider-A"), fixture("provider-A")],
                                        "2026-02-01T00:00:00Z")
        self.assertIn("source:1:duplicate_or_missing", result["issues"])

    def test_conflicting_score_is_blocked(self):
        second = fixture("provider-B")
        second["away_goals"] = 3
        result = verify_fixture_sources([fixture("provider-A"), second],
                                        "2026-02-01T00:00:00Z")
        self.assertIn("sources:fixture_conflict", result["issues"])

    def test_future_fixture_is_blocked(self):
        result = verify_fixture_sources([fixture("provider-A"), fixture("provider-B")],
                                        "2025-12-31T00:00:00Z")
        self.assertTrue(any("kickoff_invalid_or_future" in x for x in result["issues"]))

    def test_unverified_source_is_blocked(self):
        second = fixture("provider-B")
        second["verified"] = False
        result = verify_fixture_sources([fixture("provider-A"), second],
                                        "2026-02-01T00:00:00Z")
        self.assertIn("source:1:unverified", result["issues"])

    def test_missing_source_is_blocked(self):
        result = verify_fixture_sources([fixture("provider-A")], "2026-02-01T00:00:00Z")
        self.assertIn("sources:insufficient", result["issues"])


if __name__ == "__main__":
    unittest.main()
