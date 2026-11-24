import datetime as dt
import unittest

from ex_history_archive import utc
from ex_retrospective import build_examples, settled_facts, workload
from run_ex_prematch_archive import summary
from run_ex_retrospective import deduplicate_scores


class RetrospectiveTests(unittest.TestCase):
    def test_only_prior_final_whistles_feed_target(self):
        start = utc("2026-09-01T12:00:00Z")
        target_kickoff = start + dt.timedelta(days=12)
        rows = []
        for side, club in (("home", "10"), ("away", "20")):
            for i in range(7):
                kickoff = target_kickoff - dt.timedelta(days=i if i else 1, hours=12)
                terminal = target_kickoff if i == 0 else kickoff + dt.timedelta(hours=2)
                teams = {side: club, "away" if side == "home" else "home": str(i + 30)}
                rows.append({"event_id": side + str(i), "kickoff": kickoff, "finished": terminal,
                             "competition": "eng.1", "season": 2026, "teams": teams,
                             "score": (0, 3) if side == "away" and i else (3, 0)})
        target = {"event_id": "target", "kickoff": target_kickoff,
                  "finished": target_kickoff + dt.timedelta(hours=2), "score": (4, 1), "season": 2026,
                  "competition": "eng.1", "teams": {"away": "20", "home": "10"}}
        future = {**target, "event_id": "future", "kickoff": target_kickoff + dt.timedelta(days=1),
                  "finished": target_kickoff + dt.timedelta(days=1, hours=2), "score": (0, 0)}
        expected = next(r for r in build_examples([*rows, target, future]) if r["event_id"] == "target")
        self.assertEqual(expected["short"]["2.5_UST"], 1)
        self.assertEqual(expected["short"]["MS1"], .5)
        self.assertEqual(expected, next(r for r in build_examples([*rows[1:], target])
                                        if r["event_id"] == "target"))

    def test_missing_whistle_uses_observed_completed_capture_not_estimate(self):
        event = {"event_id": "17", "competition": "eng.1", "teams": {"home": "4", "away": "5"},
                 "kickoff_at": "2026-09-01T12:00:00Z"}
        fixture = {"status": {"type": {"name": "STATUS_FULL_TIME", "completed": True}},
                   "competitors": [{"homeAway": "home", "score": "3"}, {"homeAway": "away", "score": "1"}]}
        payload = {"header": {"competitions": [fixture]}}
        facts = settled_facts(payload, event, "2026-09-05T12:00:00Z")
        self.assertEqual(facts["finished"], utc("2026-09-05T12:00:00Z"))
        self.assertEqual(facts["terminal_source"], "FINAL_STATUS_CAPTURE_UPPER_BOUND")

    def test_player_concentration_changes_with_rotation(self):
        cutoff = utc("2026-09-05T12:00:00Z")
        match = {"kickoff": cutoff - dt.timedelta(days=1), "finished": cutoff - dt.timedelta(hours=22),
                 "index_team": "t", "minutes": {"t": {str(i): 90 for i in range(11)}}}
        rotated = {**match, "minutes": {"t": {str(i): 90 for i in range(11, 22)}}}
        self.assertEqual(1, workload([match, match], cutoff)[1][-1])
        self.assertEqual(.5, workload([match, rotated], cutoff)[1][-1])

    def test_prematch_summary_rejects_actual_kickoff(self):
        import json
        kickoff = utc("2026-11-25T19:00:00Z")
        sides = {"home": "10", "away": "20"}
        fixture = {"id": "17", "date": kickoff.isoformat(), "status": {"type": {"state": "pre"}},
                   "competitors": [{"homeAway": side, "team": {"id": club}} for side, club in sides.items()]}
        data = json.dumps({"header": {"id": "17", "competitions": [fixture]}})
        self.assertFalse(summary(data, kickoff - dt.timedelta(seconds=1), "17", kickoff, sides)["roster_payload_observed"])
        with self.assertRaises(ValueError):
            summary(data, kickoff, "17", kickoff, sides)

    def test_two_providers_of_the_same_result_are_one_fixture(self):
        row = {"league": "de.1", "date": "2026-11-01", "home": "A", "away": "B", "home_goals": 1, "away_goals": 2}
        ledger = {"queues": {"historical": {"provisional_matches": [row]}},
                  "alternative_bundesliga": {"queues": {"historical": {"verified": [row]}}}}
        result = deduplicate_scores(ledger)
        self.assertEqual({"ESPN+OpenLigaDB": 1}, result["by_provider_combination"])
        self.assertFalse(result["provider_overlap_proves_independence"])
