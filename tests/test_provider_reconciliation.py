import unittest
from ex_provider_reconciliation import reconcile_provider_fixtures

MAPPING = {"fixture_id": "id", "home_team": "home", "away_team": "away",
           "kickoff_at": "time", "home_goals": "hg", "away_goals": "ag"}


def provider(name, attested=True):
    return {"raw": {"id": "fixture-1", "home": "Home", "away": "Away",
                    "time": "2026-01-01T12:00:00Z", "hg": 2, "ag": 1},
            "mapping": MAPPING, "source_id": name, "provider_group": name,
            "independently_attested": attested}


class ProviderReconciliationTests(unittest.TestCase):
    def test_offset_kickoff_in_provider_blocks(self):
        first = provider("a")
        first["raw"]["time"] = "2026-01-01T15:00:00+03:00"
        result = reconcile_provider_fixtures([first, provider("b")],
                                             "2026-02-01T00:00:00Z")
        self.assertIn("provider:0:kickoff_at:invalid", result["issues"])

    def test_offset_cutoff_blocks(self):
        result = reconcile_provider_fixtures([provider("a"), provider("b")],
                                             "2026-02-01T03:00:00+03:00")
        self.assertIn("cutoff:invalid", result["issues"])

    def test_non_utc_kickoff_both_providers_blocks(self):
        first, second = provider("a"), provider("b")
        first["raw"]["time"] = "2026-01-01T15:00:00+03:00"
        second["raw"]["time"] = "2026-01-01T15:00:00+03:00"
        result = reconcile_provider_fixtures([first, second],
                                             "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")

    def test_valid_utc_sources_remain_unfinalized(self):
        result = reconcile_provider_fixtures([provider("a"), provider("b")],
                                             "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "RECONCILED_INPUT")
        self.assertFalse(result["ex_final_allowed"])

    def test_naive_kickoff_blocks(self):
        first = provider("a")
        first["raw"]["time"] = "2026-01-01T12:00:00"
        result = reconcile_provider_fixtures([first, provider("b")],
                                             "2026-02-01T00:00:00Z")
        self.assertIn("provider:0:kickoff_at:invalid", result["issues"])

    def test_two_attested_matching_sources(self):
        result = reconcile_provider_fixtures([provider("a"), provider("b")],
                                             "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "RECONCILED_INPUT")
        self.assertEqual(result["independent_sources_confirmed"], 2)
        self.assertFalse(result["ex_final_allowed"])

    def test_unattested_matching_sources_block(self):
        result = reconcile_provider_fixtures([provider("a"), provider("b", False)],
                                             "2026-02-01T00:00:00Z")
        self.assertIn("provider:1:attestation_missing", result["issues"])
        self.assertIsNone(result["agreed_fixture"])

    def test_provider_score_conflict_blocks(self):
        second = provider("b")
        second["raw"]["ag"] = 3
        result = reconcile_provider_fixtures([provider("a"), second],
                                             "2026-02-01T00:00:00Z")
        self.assertIn("sources:fixture_conflict", result["issues"])

    def test_same_provider_group_blocks(self):
        second = provider("b")
        second["provider_group"] = "a"
        result = reconcile_provider_fixtures([provider("a"), second],
                                             "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")

    def test_invalid_mapping_blocks(self):
        second = provider("b")
        second["mapping"] = {}
        result = reconcile_provider_fixtures([provider("a"), second],
                                             "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["agreed_fixture"])


if __name__ == "__main__":
    unittest.main()
