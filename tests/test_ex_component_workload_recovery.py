import unittest

from ex_component_workload_recovery import recover_team_workload
from ex_history_archive import utc


class WorkloadRecoveryTests(unittest.TestCase):
    def test_counts_completed_cup_without_inventing_finish_or_using_future_capture(self):
        schedule = {"matches_shown": [
            {"event_id": "old", "kickoff_at": "2026-11-01T20:00:00Z"},
            {"event_id": "cup", "kickoff_at": "2026-11-20T20:00:00Z"},
            {"event_id": "most_recent", "kickoff_at": "2026-11-25T20:00:00Z"},
        ]}
        captured = "2026-11-26T00:00:00Z"
        records = {}
        for row, status in zip(schedule["matches_shown"][1:], ("STATUS_FINAL_PEN", "STATUS_FULL_TIME")):
            records[row["event_id"]] = {"source": {"retrieved_at": captured, "sha256": "a" * 64},
                "fact": {"teams": {"home": "1", "away": "2"}, "kickoff": row["kickoff_at"],
                         "provider_completed": True, "terminal_status": status}}
        latest = records["most_recent"]["fact"]
        latest["terminal_source"] = "PROVIDER_END_REGULAR_TIME"
        latest["finished"] = "2026-11-25T22:00:00Z"
        kick, cut = utc("2026-11-29T20:00:00Z"), utc("2026-11-27T09:00:00Z")
        value, issue = recover_team_workload(schedule, records, "1", kick, cut)
        self.assertIsNone(issue)
        self.assertEqual((94, 2), (value["rest_hours"], value["completed_match_count"]))
        latest["terminal_source"] = "FINAL_STATUS_CAPTURE_UPPER_BOUND"
        self.assertEqual("LATEST_MATCH_FINISH_UNVERIFIED",
                         recover_team_workload(schedule, records, "1", kick, cut)[1])
        self.assertEqual("COMPLETED_MATCH_PROOF_MISSING",
                         recover_team_workload(schedule, records, "1", kick, utc(captured))[1])
