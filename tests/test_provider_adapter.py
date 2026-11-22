import unittest
from ex_provider_adapter import normalize_provider_fixture

MAPPING = {"fixture_id": "id", "home_team": "home", "away_team": "away",
           "kickoff_at": "time", "home_goals": "hg", "away_goals": "ag"}


def raw():
    return {"id": "fixture-1", "home": "Home", "away": "Away",
            "time": "2026-01-01T12:00:00Z", "hg": 2, "ag": 1}


class ProviderAdapterTests(unittest.TestCase):
    def test_normalization_does_not_verify(self):
        result = normalize_provider_fixture(raw(), MAPPING, "source-a", "provider-a")
        self.assertEqual(result["status"], "NORMALIZED_UNVERIFIED")
        self.assertEqual(result["record"]["home_goals"], 2)
        self.assertFalse(result["record"]["verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_missing_mapping_blocks(self):
        mapping = dict(MAPPING)
        del mapping["home_goals"]
        result = normalize_provider_fixture(raw(), mapping, "source-a", "provider-a")
        self.assertIn("home_goals:mapping_missing", result["issues"])

    def test_invalid_score_blocks(self):
        record = raw()
        record["hg"] = "2"
        result = normalize_provider_fixture(record, MAPPING, "source-a", "provider-a")
        self.assertIn("home_goals:invalid", result["issues"])

    def test_missing_provider_group_blocks(self):
        result = normalize_provider_fixture(raw(), MAPPING, "source-a", "")
        self.assertIn("provider_group:missing", result["issues"])

    def test_non_utc_timestamp_blocks(self):
        record = raw()
        record["time"] = "2026-01-01T12:00:00"
        result = normalize_provider_fixture(record, MAPPING, "source-a", "provider-a")
        self.assertIn("kickoff_at:invalid", result["issues"])


if __name__ == "__main__":
    unittest.main()
