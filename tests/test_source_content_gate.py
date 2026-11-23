import hashlib
import json
import unittest
from ex_source_content_gate import compare_source_content


FACTS = {"fixture_id": "m1", "home_team": "A", "away_team": "B",
         "kickoff_at": "2026-01-01T12:00:00Z", "home_goals": 2, "away_goals": 1}


def captured(provider, facts=FACTS):
    snapshot = json.dumps(facts, sort_keys=True, separators=(",", ":"))
    # Different source-page snapshots may contain different provider-specific
    # metadata, while the required fixture fields remain identical.
    snapshot = json.dumps(dict(facts, publisher=provider), sort_keys=True)
    return {"provider_group": provider, "captured_content": snapshot,
            "content_sha256": hashlib.sha256(snapshot.encode()).hexdigest()}


class ContentGateTests(unittest.TestCase):
    def test_matching_content_is_not_official_or_final(self):
        result = compare_source_content([captured("A"), captured("B")], FACTS)
        self.assertEqual(result["status"], "CONTENT_CONSISTENT_UNATTESTED")
        self.assertFalse(result["content_verified_by_live_fetch"])
        self.assertFalse(result["official_source_attested"])
        self.assertFalse(result["ex_final_allowed"])

    def test_conflicting_score_blocks(self):
        bad = dict(FACTS, home_goals=3)
        result = compare_source_content([captured("A"), captured("B", bad)], FACTS)
        self.assertIn("source:1:fixture_content_conflict", result["issues"])

    def test_tampered_digest_blocks(self):
        row = captured("B")
        row["content_sha256"] = "0" * 64
        result = compare_source_content([captured("A"), row], FACTS)
        self.assertIn("source:1:content_digest_mismatch", result["issues"])

    def test_identical_snapshot_blocks(self):
        row = captured("A")
        result = compare_source_content([row, dict(row, provider_group="B")], FACTS)
        self.assertIn("source:1:identical_snapshot", result["issues"])

    def test_duplicate_provider_blocks(self):
        result = compare_source_content([captured("A"), captured("A")], FACTS)
        self.assertIn("source:1:provider_duplicate_or_missing", result["issues"])

    def test_unstructured_content_blocks(self):
        row = captured("B")
        row["captured_content"] = "A beat B 2-1"
        row["content_sha256"] = hashlib.sha256(row["captured_content"].encode()).hexdigest()
        result = compare_source_content([captured("A"), row], FACTS)
        self.assertIn("source:1:content_not_structured", result["issues"])


if __name__ == "__main__":
    unittest.main()
