import unittest
from ex_provenance_audit import validate_provenance


def evidence(name):
    return {"provider_group": name, "evidence_id": name + "-evidence",
            "reviewer_id": name + "-reviewer", "fixture_id": "fixture-1",
            "evidence_url": "https://example.org/" + name,
            "reviewed_at": "2026-01-03T12:00:00Z"}


class ProvenanceAuditTests(unittest.TestCase):
    def test_metadata_ready_is_not_external_verification(self):
        result = validate_provenance([evidence("a"), evidence("b")],
                                     "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "PROVENANCE_METADATA_READY_UNVERIFIED")
        self.assertFalse(result["externally_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_duplicate_evidence_blocks(self):
        second = evidence("b")
        second["evidence_id"] = "a-evidence"
        result = validate_provenance([evidence("a"), second], "2026-02-01T00:00:00Z")
        self.assertIn("attestation:1:evidence_duplicate_or_missing", result["issues"])

    def test_duplicate_group_blocks(self):
        second = evidence("b")
        second["provider_group"] = "a"
        result = validate_provenance([evidence("a"), second], "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")

    def test_insecure_url_blocks(self):
        second = evidence("b")
        second["evidence_url"] = "http://example.org/b"
        result = validate_provenance([evidence("a"), second], "2026-02-01T00:00:00Z")
        self.assertIn("attestation:1:url_invalid", result["issues"])

    def test_malformed_ipv6_url_blocks_without_crash(self):
        second = evidence("b")
        second["evidence_url"] = "https://[broken-ipv6/b"
        result = validate_provenance([evidence("a"), second], "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("attestation:1:url_invalid", result["issues"])

    def test_duplicate_url_with_different_evidence_id_blocks(self):
        second = evidence("b")
        second["evidence_url"] = "https://example.org/a/"
        result = validate_provenance([evidence("a"), second], "2026-02-01T00:00:00Z")
        self.assertIn("attestation:1:url_duplicate", result["issues"])

    def test_same_reviewer_across_providers_blocks(self):
        second = evidence("b")
        second["reviewer_id"] = "a-reviewer"
        result = validate_provenance([evidence("a"), second], "2026-02-01T00:00:00Z")
        self.assertIn("attestation:1:reviewer_duplicate", result["issues"])

    def test_invalid_url_port_blocks_without_crash(self):
        second = evidence("b")
        second["evidence_url"] = "https://example.org:bad/b"
        result = validate_provenance([evidence("a"), second], "2026-02-01T00:00:00Z")
        self.assertIn("attestation:1:url_invalid", result["issues"])

    def test_fixture_mismatch_blocks(self):
        second = evidence("b")
        second["fixture_id"] = "other-fixture"
        result = validate_provenance([evidence("a"), second], "2026-02-01T00:00:00Z")
        self.assertIn("attestations:fixture_conflict", result["issues"])

    def test_future_review_blocks(self):
        second = evidence("b")
        second["reviewed_at"] = "2026-03-01T00:00:00Z"
        result = validate_provenance([evidence("a"), second], "2026-02-01T00:00:00Z")
        self.assertIn("attestation:1:date_invalid_or_future", result["issues"])


if __name__ == "__main__":
    unittest.main()
