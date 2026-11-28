import unittest
from ex_source_agreement import verify_fixture_sources


def fixture(source):
    return {"source_id": source, "provider_group": source, "verified": True, "fixture_id": "match-1",
            "home_team": "Home", "away_team": "Away",
            "kickoff_at": "2026-01-01T12:00:00Z", "home_goals": 2, "away_goals": 1}


class SourceAgreementTests(unittest.TestCase):
    def test_missing_home_team_blocks_without_exception(self):
        second = fixture("provider-B")
        del second["home_team"]
        result = verify_fixture_sources([fixture("provider-A"), second],
                                        "2026-02-01T00:00:00Z")
        self.assertIn("source:1:fields_missing", result["issues"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_missing_goals_blocks_without_exception(self):
        second = fixture("provider-B")
        del second["home_goals"]
        result = verify_fixture_sources([fixture("provider-A"), second],
                                        "2026-02-01T00:00:00Z")
        self.assertIn("source:1:fields_missing", result["issues"])

    def test_missing_kickoff_blocks_without_exception(self):
        second = fixture("provider-B")
        del second["kickoff_at"]
        result = verify_fixture_sources([fixture("provider-A"), second],
                                        "2026-02-01T00:00:00Z")
        self.assertIn("source:1:fields_missing", result["issues"])

    def test_missing_fields_in_both_sources_blocks(self):
        first, second = fixture("provider-A"), fixture("provider-B")
        del first["fixture_id"]
        del second["away_goals"]
        result = verify_fixture_sources([first, second], "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["agreed_fixture"])

    def test_non_dict_source_blocks_without_exception(self):
        result = verify_fixture_sources([fixture("provider-A"), None],
                                        "2026-02-01T00:00:00Z")
        self.assertIn("source:1:invalid", result["issues"])

    def test_offset_cutoff_is_blocked(self):
        result = verify_fixture_sources([fixture("provider-A"), fixture("provider-B")],
                                        "2026-02-01T03:00:00+03:00")
        self.assertIn("cutoff:invalid", result["issues"])

    def test_offset_kickoff_is_blocked(self):
        second = fixture("provider-B")
        second["kickoff_at"] = "2026-01-01T15:00:00+03:00"
        result = verify_fixture_sources([fixture("provider-A"), second],
                                        "2026-02-01T00:00:00Z")
        self.assertIn("source:1:kickoff_invalid_or_future", result["issues"])

    def test_both_sources_offset_kickoff_are_blocked(self):
        first, second = fixture("provider-A"), fixture("provider-B")
        first["kickoff_at"] = "2026-01-01T15:00:00+03:00"
        second["kickoff_at"] = "2026-01-01T15:00:00+03:00"
        result = verify_fixture_sources([first, second], "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")

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

    def test_same_provider_under_two_names_is_blocked(self):
        second = fixture("provider-B")
        second["provider_group"] = "provider-A"
        result = verify_fixture_sources([fixture("provider-A"), second],
                                        "2026-02-01T00:00:00Z")
        self.assertIn("source:1:provider_group_duplicate_or_missing", result["issues"])

    def test_provider_group_missing_is_blocked(self):
        second = fixture("provider-B")
        del second["provider_group"]
        result = verify_fixture_sources([fixture("provider-A"), second],
                                        "2026-02-01T00:00:00Z")
        self.assertIn("source:1:provider_group_duplicate_or_missing", result["issues"])

    def test_unhashable_identity_blocks_without_crash(self):
        second = fixture("provider-B")
        second["home_team"] = ["Home"]
        result = verify_fixture_sources([fixture("provider-A"), second],
                                        "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("source:1:identity_invalid", result["issues"])

    def test_unhashable_score_blocks_without_crash(self):
        second = fixture("provider-B")
        second["home_goals"] = {"goals": 2}
        result = verify_fixture_sources([fixture("provider-A"), second],
                                        "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("source:1:score_invalid", result["issues"])


    def test_strict_mode_requires_evidence_locator(self):
        result = verify_fixture_sources([fixture("provider-A"), fixture("provider-B")],
                                        "2026-02-01T00:00:00Z", require_evidence_locator=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("source:0:evidence_url_missing_or_invalid", result["issues"])

    def test_strict_mode_accepts_explicit_locators(self):
        a, b = fixture("provider-A"), fixture("provider-B")
        for row in (a, b):
            row["evidence_url"] = "https://example.org/fixture/" + row["source_id"]
            row["retrieved_at"] = "2026-01-02T00:00:00Z"
        result = verify_fixture_sources([a, b], "2026-02-01T00:00:00Z",
                                        require_evidence_locator=True)
        self.assertEqual(result["status"], "CROSS_VERIFIED_INPUT")
        self.assertFalse(result["ex_final_allowed"])

    def test_out_of_range_score_rejected(self):
        a, b = fixture("provider-A"), fixture("provider-B")
        a["home_goals"] = b["home_goals"] = 31
        result = verify_fixture_sources([a, b], "2026-02-01T00:00:00Z")
        self.assertIn("source:0:score_invalid", result["issues"])


    def test_strict_mode_rejects_retrieval_after_cutoff(self):
        a, b = fixture("provider-A"), fixture("provider-B")
        for row in (a, b):
            row["evidence_url"] = "https://example.org/results"
            row["retrieved_at"] = "2026-03-01T00:00:00Z"
        result = verify_fixture_sources([a, b], "2026-02-01T00:00:00Z",
                                        require_evidence_locator=True)
        self.assertIn("source:0:retrieved_at_missing_or_invalid", result["issues"])

    def test_strict_mode_rejects_retrieval_before_kickoff(self):
        a, b = fixture("provider-A"), fixture("provider-B")
        for row in (a, b):
            row["evidence_url"] = "https://example.org/results"
            row["retrieved_at"] = "2025-12-31T00:00:00Z"
        result = verify_fixture_sources([a, b], "2026-02-01T00:00:00Z",
                                        require_evidence_locator=True)
        self.assertIn("source:0:retrieved_at_missing_or_invalid", result["issues"])

    def test_strict_mode_rejects_malformed_https_url(self):
        a, b = fixture("provider-A"), fixture("provider-B")
        for row in (a, b):
            row["evidence_url"] = "https:///missing-host"
            row["retrieved_at"] = "2026-01-02T00:00:00Z"
        result = verify_fixture_sources([a, b], "2026-02-01T00:00:00Z",
                                        require_evidence_locator=True)
        self.assertIn("source:0:evidence_url_missing_or_invalid", result["issues"])

    def test_strict_mode_blocks_reused_evidence_url(self):
        a, b = fixture("provider-A"), fixture("provider-B")
        for row in (a, b):
            row["evidence_url"] = "https://example.org/fixture/1"
            row["retrieved_at"] = "2026-01-02T00:00:00Z"
        result = verify_fixture_sources([a, b], "2026-02-01T00:00:00Z",
                                        require_evidence_locator=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("source:1:duplicate_evidence_url", result["issues"])

    def test_strict_mode_blocks_localhost_evidence(self):
        a, b = fixture("provider-A"), fixture("provider-B")
        for row in (a, b):
            row["evidence_url"] = "https://localhost/fixture/1"
            row["retrieved_at"] = "2026-01-02T00:00:00Z"
        result = verify_fixture_sources([a, b], "2026-02-01T00:00:00Z",
                                        require_evidence_locator=True)
        self.assertIn("source:0:evidence_url_missing_or_invalid", result["issues"])

    def test_strict_mode_blocks_custom_port(self):
        a, b = fixture("provider-A"), fixture("provider-B")
        for row in (a, b):
            row["evidence_url"] = "https://example.org:8443/fixture/1"
            row["retrieved_at"] = "2026-01-02T00:00:00Z"
        result = verify_fixture_sources([a, b], "2026-02-01T00:00:00Z",
                                        require_evidence_locator=True)
        self.assertIn("source:0:evidence_url_missing_or_invalid", result["issues"])

    def test_strict_mode_detects_case_variant_duplicate_host(self):
        a, b = fixture("provider-A"), fixture("provider-B")
        a["evidence_url"] = "https://EXAMPLE.org/fixture/1"
        b["evidence_url"] = "https://example.org/fixture/1"
        for row in (a, b):
            row["retrieved_at"] = "2026-01-02T00:00:00Z"
        result = verify_fixture_sources([a, b], "2026-02-01T00:00:00Z",
                                        require_evidence_locator=True)
        self.assertIn("source:1:duplicate_evidence_url", result["issues"])

    def test_missing_source_is_blocked(self):
        result = verify_fixture_sources([fixture("provider-A")], "2026-02-01T00:00:00Z")
        self.assertIn("sources:insufficient", result["issues"])


    def test_archived_pair_rejects_shared_upstream_and_late_review(self):
        from datetime import datetime, timezone
        from ex_source_agreement import verify_archived_score_pair

        fixture = {"fixture_id": "1", "home_team": "2", "away_team": "3", "league": "en.1",
                   "kickoff_at": "2026-11-25T20:00:00Z", "home_goals": 2, "away_goals": 1}
        sources = [{"url": f"https://{host}/match", "sha256": value * 64}
                   for host, value in (("example.com", "a"), ("example.org", "b"))]
        observations = [{"source": source, "sealed_at": "2026-11-26T01:00:00Z"} for source in sources]
        reviewed = {source["sha256"]: {"source_url": source["url"], "reviewed_at": "2026-11-26T02:00:00Z",
                    "review_locator": source["url"], "producer_id": source["sha256"],
                    "upstream_ids": [source["sha256"]], "parse_score": lambda *_: fixture} for source in sources}
        def loader(source, url):
            return url.encode(), datetime(2026, 11, 26, tzinfo=timezone.utc)
        def status():
            return verify_archived_score_pair(observations, fixture, "2026-11-26T03:00:00Z", loader, reviewed)["status"]
        self.assertEqual("CROSS_VERIFIED_INPUT", status())
        reviewed["b" * 64]["upstream_ids"] = ["A" * 64]
        self.assertEqual("BLOCKED", status())
        reviewed["b" * 64]["upstream_ids"] = ["b" * 64]
        reviewed["b" * 64]["reviewed_at"] = "2026-11-26T03:00:00Z"
        self.assertEqual("BLOCKED", status())


if __name__ == "__main__":
    unittest.main()
