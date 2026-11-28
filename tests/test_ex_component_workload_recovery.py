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
        approximate, issue = recover_team_workload(schedule, records, "1", kick, cut, allow_kickoff_proxy=True)
        self.assertIsNone(issue)
        self.assertEqual("KICKOFF_TO_KICKOFF_PROXY", approximate["basis"])
        self.assertEqual(96, approximate["kickoff_gap_hours"])
        self.assertNotIn("rest_hours", approximate)
        self.assertEqual("COMPLETED_MATCH_PROOF_MISSING",
                         recover_team_workload(schedule, records, "1", kick, utc(captured),
                                               allow_kickoff_proxy=True)[1])
        self.assertEqual("COMPLETED_MATCH_PROOF_MISSING",
                         recover_team_workload(schedule, records, "1", kick, utc(captured))[1])

    def test_hoffenheim_europa_completion_recovers_load_by_event_identity(self):
        import json
        from ex_component_workload_recovery import parse_completion

        event = "401915515"
        kickoff = utc("2026-11-29T16:30Z")
        cutoff = utc("2026-11-27T12:31Z")
        league_game = {"event_id": "401884734", "kickoff_at": "2026-11-21T14:30Z"}
        europa_game = {"event_id": event, "kickoff_at": "2026-11-26T20:00Z",
                       "teams": {"home": "7911", "away": "3746"}}
        schedule = {"matches_shown": [
            {"event_id": "older", "kickoff_at": "2026-11-08T18:30Z"}, league_game, europa_game]}
        before = {league_game["event_id"]: {
            "fact": {"kickoff": league_game["kickoff_at"], "teams": {"home": "7911"},
                     "provider_completed": True, "terminal_status": "STATUS_FULL_TIME"},
            "source": {"retrieved_at": "2026-11-24T17:32Z", "sha256": "a" * 64}}}
        self.assertEqual("COMPLETED_MATCH_PROOF_MISSING",
                         recover_team_workload(schedule, before, "7911", kickoff, cutoff,
                                               allow_kickoff_proxy=True)[1])
        payload = {"header": {"id": event, "league": {"slug": "uefa.europa"},
                   "competitions": [{"id": event, "date": europa_game["kickoff_at"],
                   "status": {"type": {"state": "post", "completed": True, "name": "STATUS_FULL_TIME"}},
                   "competitors": [{"homeAway": side, "team": {"id": team}}
                                   for side, team in europa_game["teams"].items()]}]}}
        fetched = utc("2026-11-27T12:30Z")
        raw = json.dumps(payload)
        fact = parse_completion(raw, fetched, event, [("7911", europa_game)])
        after = {**before, event: {"fact": fact, "source": {"retrieved_at": fetched.isoformat(), "sha256": "b" * 64}}}
        result, issue = recover_team_workload(schedule, after, "7911", kickoff, cutoff, allow_kickoff_proxy=True)
        self.assertIsNone(issue)
        self.assertEqual((68.5, 2), (result["kickoff_gap_hours"], result["completed_match_count"]))
        self.assertEqual("uefa.europa", fact["competition"])
        with self.assertRaises(ValueError):
            parse_completion(raw, fetched, event, [("unexpected", europa_game)])
