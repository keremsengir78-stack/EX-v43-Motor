import unittest

from ex_historical_features import provider_context
from ex_history_environment import coordinates, separation_km
from run_ex_history_merge import assemble


class HistoryBulkTests(unittest.TestCase):
    def test_merge_requires_correct_partition_and_identity(self):
        event = {"event_id": "2", "kickoff_at": "2026-11-20T15:00:00Z", "competition": "eng.1",
                 "teams": {"home": "4", "away": "9"}}
        plan = {"pending_events": [event]}
        detail = {**event, "completed": True, "venue": None, "player_rows": []}
        first = {"shards": 2, "shard": 0, "assigned": 1, "match_details": [detail]}
        second = {"shards": 2, "shard": 1, "assigned": 0, "match_details": []}
        _, coverage = assemble(plan, [first, second])
        self.assertEqual(1, coverage["eng.1"]["summary_fraction"])
        with self.assertRaisesRegex(ValueError, "ownership"):
            assemble(plan, [first, {**second, "match_details": [detail]}])

    def test_shared_context_rejects_player_data_captured_after_cutoff(self):
        game = {"event_id": "1", "completed": True, "kickoff_at": "2026-11-20T15:00:00Z",
                "teams": {"home": "1", "away": "2"}}
        calendar = {"team_id": "1", "source": {"retrieved_at": "2026-11-21T10:00:00Z"}, "fixtures": [game]}
        detail = {**game, "source": {"retrieved_at": "2026-11-23T10:00:00Z"},
                  "player_rows": [{"team_id": "1", "athlete_id": "5", "provider_minutes": None,
                                   "nominal_regulation_minutes": 90}]}
        early = provider_context(calendar, {"1": detail}, "2026-11-22T10:00:00Z")
        late = provider_context(calendar, {"1": detail}, "2026-11-24T10:00:00Z")
        self.assertEqual(1, early["observed_matches_14d"])
        self.assertEqual({}, early["nominal_minutes_14d"])
        self.assertEqual({"5": 90}, late["nominal_minutes_14d"])
        self.assertFalse(late["verified_component_scores"])

    def test_venue_identity_and_geodesic(self):
        registry = {"1": {"name": "A", "latitude": 0, "longitude": 0, "source": "official"}}
        self.assertIsNone(coordinates({"id": "1", "fullName": "B"}, registry))
        self.assertEqual((0, 0), coordinates({"id": "1", "fullName": "A"}, registry))
        self.assertAlmostEqual(111.20, separation_km((0, 0), (0, 1)), places=2)
