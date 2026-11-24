"""Regression coverage for Unicode identity spoofing in captured source evidence."""
import hashlib
import json
import unittest

from ex_source_content_gate import compare_source_content


FACTS = {"fixture_id": "unicode-fixture", "home_team": "Real Madrid",
         "away_team": "Barcelona", "kickoff_at": "2026-01-01T12:00:00Z",
         "home_goals": 2, "away_goals": 1}


def observation(group):
    snapshot = json.dumps(dict(FACTS, publisher=group), ensure_ascii=False)
    return {"provider_group": group, "captured_content": snapshot,
            "content_sha256": hashlib.sha256(snapshot.encode("utf-8")).hexdigest()}


class UnicodeIdentitySafetyTests(unittest.TestCase):
    def test_unicode_compatibility_provider_alias_is_not_independent(self):
        result = compare_source_content(
            [observation("Source A"), observation("Ｓｏｕｒｃｅ A")], FACTS)
        self.assertIn("source:1:provider_duplicate_or_missing", result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_internal_whitespace_alias_is_not_independent(self):
        result = compare_source_content(
            [observation("Source A"), observation("Source\u00a0  A")], FACTS)
        self.assertIn("source:1:provider_duplicate_or_missing", result["issues"])

    def test_same_team_with_unicode_compatibility_is_invalid(self):
        facts = dict(FACTS, away_team="Ｒｅａｌ  Madrid")
        result = compare_source_content([observation("A"), observation("B")], facts)
        self.assertIn("expected:invalid_fixture_facts", result["issues"])

    def test_publisher_alias_normalization_does_not_certify_origin(self):
        row = observation("Ｓｏｕｒｃｅ A")
        row["provider_group"] = "Source A"
        result = compare_source_content([observation("Source B"), row], FACTS)
        self.assertEqual(result["status"], "CONTENT_CONSISTENT_UNATTESTED")
        self.assertFalse(result["official_source_attested"])
        self.assertFalse(result["editorial_independence_attested"])


    def test_invalid_utf8_snapshot_is_blocked(self):
        row = observation("A")
        row["captured_content"] = "\ud800"
        result = compare_source_content([row, observation("B")], FACTS)
        self.assertIn("source:0:content_invalid_unicode", result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_deeply_nested_snapshot_is_blocked(self):
        row = observation("A")
        snapshot = "[" * 10000 + "0" + "]" * 10000
        row["captured_content"] = snapshot
        row["content_sha256"] = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
        result = compare_source_content([row, observation("B")], FACTS)
        self.assertIn("source:0:content_not_structured", result["issues"])
        self.assertFalse(result["ex_final_allowed"])


if __name__ == "__main__":
    unittest.main()
