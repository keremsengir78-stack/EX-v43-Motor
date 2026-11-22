import unittest
from ex_provenance_pipeline import reconcile_with_provenance

MAPPING = {"fixture_id": "id", "home_team": "home", "away_team": "away",
           "kickoff_at": "time", "home_goals": "hg", "away_goals": "ag"}
CUTOFF = "2026-02-01T00:00:00Z"


def provider(name):
    return {"raw": {"id": "fixture-1", "home": "Home", "away": "Away",
                    "time": "2026-01-01T12:00:00Z", "hg": 2, "ag": 1},
            "mapping": MAPPING, "source_id": name, "provider_group": name,
            "independently_attested": True}


def evidence(name):
    return {"provider_group": name, "evidence_id": name + "-evidence",
            "reviewer_id": name + "-reviewer", "fixture_id": "fixture-1",
            "evidence_url": "https://example.org/" + name,
            "reviewed_at": "2026-01-03T12:00:00Z"}


def settlements():
    return [{"provider_group": group, "fixture_id": "fixture-1",
             "status": "finished", "settled_at": "2026-01-01T15:00:00Z"}
            for group in ("a", "b")]


class ProvenancePipelineTests(unittest.TestCase):
    def test_missing_settlement_blocks(self):
        result = reconcile_with_provenance([provider("a"), provider("b")],
                                           [evidence("a"), evidence("b")], CUTOFF)
        self.assertIn("settlement:missing", result["issues"])

    def test_live_settlement_blocks(self):
        rows = settlements()
        rows[1]["status"] = "live"
        result = reconcile_with_provenance([provider("a"), provider("b")],
                                           [evidence("a"), evidence("b")], CUTOFF, rows)
        self.assertIn("settlement:settlement:1:not_finished", result["issues"])

    def test_review_before_provider_settlement_blocks(self):
        rows = settlements()
        rows[1]["settled_at"] = "2026-01-04T15:00:00Z"
        result = reconcile_with_provenance([provider("a"), provider("b")],
                                           [evidence("a"), evidence("b")], CUTOFF, rows)
        self.assertIn("provenance:review_before_settlement", result["issues"])

    def test_review_after_provider_settlement_passes_metadata_gate(self):
        rows = settlements()
        rows[1]["settled_at"] = "2026-01-02T15:00:00Z"
        result = reconcile_with_provenance([provider("a"), provider("b")],
                                           [evidence("a"), evidence("b")], CUTOFF, rows)
        self.assertEqual(result["status"], "RECONCILED_WITH_METADATA_UNVERIFIED")
        self.assertFalse(result["externally_verified"])

    def test_settlement_provider_group_mismatch_blocks(self):
        rows = settlements()
        rows[1]["provider_group"] = "c"
        result = reconcile_with_provenance([provider("a"), provider("b")],
                                           [evidence("a"), evidence("b")], CUTOFF, rows)
        self.assertIn("settlement:provider_group_mismatch", result["issues"])

    def test_consistent_metadata_still_unverified(self):
        result = reconcile_with_provenance([provider("a"), provider("b")],
                                           [evidence("a"), evidence("b")], CUTOFF, settlements())
        self.assertEqual(result["status"], "RECONCILED_WITH_METADATA_UNVERIFIED")
        self.assertFalse(result["externally_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_wrong_provider_group_blocks(self):
        result = reconcile_with_provenance([provider("a"), provider("b")],
                                           [evidence("a"), evidence("c")], CUTOFF, settlements())
        self.assertIn("provenance:provider_group_mismatch", result["issues"])

    def test_wrong_fixture_attestation_blocks(self):
        second = evidence("b")
        second["fixture_id"] = "fixture-2"
        result = reconcile_with_provenance([provider("a"), provider("b")],
                                           [evidence("a"), second], CUTOFF, settlements())
        self.assertEqual(result["status"], "BLOCKED")

    def test_unattested_provider_blocks(self):
        second = provider("b")
        second["independently_attested"] = False
        result = reconcile_with_provenance([provider("a"), second],
                                           [evidence("a"), evidence("b")], CUTOFF, settlements())
        self.assertEqual(result["status"], "BLOCKED")

    def test_review_before_kickoff_blocks(self):
        second = evidence("b")
        second["reviewed_at"] = "2025-12-31T12:00:00Z"
        result = reconcile_with_provenance([provider("a"), provider("b")],
                                           [evidence("a"), second], CUTOFF, settlements())
        self.assertIn("provenance:review_before_or_at_kickoff", result["issues"])

    def test_review_at_kickoff_blocks(self):
        second = evidence("b")
        second["reviewed_at"] = "2026-01-01T12:00:00Z"
        result = reconcile_with_provenance([provider("a"), provider("b")],
                                           [evidence("a"), second], CUTOFF, settlements())
        self.assertIn("provenance:review_before_or_at_kickoff", result["issues"])

    def test_conflicting_scores_block(self):
        second = provider("b")
        second["raw"]["ag"] = 3
        result = reconcile_with_provenance([provider("a"), second],
                                           [evidence("a"), evidence("b")], CUTOFF, settlements())
        self.assertEqual(result["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
