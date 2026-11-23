import hashlib
import json
import unittest

from ex_captured_evidence_audit import audit_captured_fixture_evidence

EXPECTED = {
    "fixture_id": "fixture-42",
    "home_team": "Home",
    "away_team": "Away",
    "kickoff_at": "2026-11-23T12:00:00Z",
    "home_goals": 2,
    "away_goals": 1,
}
CHECKED = "2026-11-23T14:10:00Z"


def source(provider, **changes):
    snapshot = json.dumps(dict(EXPECTED, publisher=provider), sort_keys=True)
    row = {
        "provider_group": provider,
        "captured_content": snapshot,
        "content_sha256": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
        "published_at": "2026-11-23T14:00:00Z",
        "captured_at": "2026-11-23T14:05:00Z",
    }
    row.update(changes)
    return row


class CapturedEvidenceAuditTests(unittest.TestCase):
    def test_consistent_but_unattested(self):
        result = audit_captured_fixture_evidence(
            [source("publisher-a"), source("publisher-b")], EXPECTED, CHECKED)
        self.assertEqual(result["status"], "CONSISTENT_UNATTESTED")
        self.assertEqual(result["issues"], [])
        self.assertFalse(result["live_fetch_attested"])
        self.assertFalse(result["official_source_attested"])
        self.assertFalse(result["editorial_independence_attested"])
        self.assertFalse(result["ex_final_allowed"])

    def test_stale_capture_blocks_even_when_content_agrees(self):
        result = audit_captured_fixture_evidence(
            [source("publisher-a", captured_at="2026-11-20T14:05:00Z"),
             source("publisher-b")], EXPECTED, CHECKED)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("captured_before_publication" in x for x in result["issues"]))

    def test_missing_time_metadata_blocks(self):
        row = source("publisher-a")
        del row["published_at"]
        result = audit_captured_fixture_evidence(
            [row, source("publisher-b")], EXPECTED, CHECKED)
        self.assertIn("source:0:time:invalid_timestamp", result["issues"])

    def test_content_mismatch_blocks_with_consistent_times(self):
        row = source("publisher-a", content_sha256="0" * 64)
        result = audit_captured_fixture_evidence(
            [row, source("publisher-b")], EXPECTED, CHECKED)
        self.assertIn("content:source:0:content_digest_mismatch", result["issues"])

    def test_invalid_input_fails_closed(self):
        result = audit_captured_fixture_evidence(None, EXPECTED, CHECKED)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ex_final_allowed"])

    def test_invalid_age_setting_fails_closed(self):
        result = audit_captured_fixture_evidence(
            [source("publisher-a"), source("publisher-b")], EXPECTED, CHECKED,
            maximum_capture_age_seconds=True)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("invalid_maximum_age" in x for x in result["issues"]))


if __name__ == "__main__":
    unittest.main()
