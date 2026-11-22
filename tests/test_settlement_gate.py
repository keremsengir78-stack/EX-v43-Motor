import unittest
from ex_settlement_gate import verify_settlement_records

KICKOFF = "2026-01-01T12:00:00Z"
CUTOFF = "2026-02-01T00:00:00Z"


def record(group):
    return {"provider_group": group, "fixture_id": "fixture-1",
            "status": "finished", "settled_at": "2026-01-01T15:00:00Z"}


class SettlementGateTests(unittest.TestCase):
    def test_finished_results_are_metadata_only(self):
        result = verify_settlement_records([record("a"), record("b")],
                                           "fixture-1", KICKOFF, CUTOFF)
        self.assertEqual(result["status"], "SETTLEMENT_METADATA_READY_UNVERIFIED")
        self.assertFalse(result["externally_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_live_match_blocks(self):
        second = record("b")
        second["status"] = "live"
        result = verify_settlement_records([record("a"), second],
                                           "fixture-1", KICKOFF, CUTOFF)
        self.assertIn("settlement:1:not_finished", result["issues"])

    def test_settlement_before_kickoff_blocks(self):
        second = record("b")
        second["settled_at"] = "2026-01-01T11:00:00Z"
        result = verify_settlement_records([record("a"), second],
                                           "fixture-1", KICKOFF, CUTOFF)
        self.assertIn("settlement:1:time_invalid", result["issues"])

    def test_duplicate_provider_blocks(self):
        result = verify_settlement_records([record("a"), record("a")],
                                           "fixture-1", KICKOFF, CUTOFF)
        self.assertEqual(result["status"], "BLOCKED")

    def test_fixture_mismatch_blocks(self):
        second = record("b")
        second["fixture_id"] = "other"
        result = verify_settlement_records([record("a"), second],
                                           "fixture-1", KICKOFF, CUTOFF)
        self.assertIn("settlement:1:fixture_mismatch", result["issues"])


if __name__ == "__main__":
    unittest.main()
