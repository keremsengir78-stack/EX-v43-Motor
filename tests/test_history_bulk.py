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


class HistorySourceFallbackTests(unittest.TestCase):
    def test_denied_source_uses_stored_retry_category(self):
        from tempfile import TemporaryDirectory
        from urllib.error import HTTPError
        from ex_history_archive import HistoryArchive, RetryDeferred, failure_class

        url = "https://archive-api.open-meteo.com/v1/archive"

        def denied(_):
            raise HTTPError(url, 403, "Forbidden", {}, None)

        with TemporaryDirectory() as root:
            archive = HistoryArchive(root, 4, fetch=denied)
            with self.assertRaises(HTTPError):
                archive.get(url, lambda raw, _: raw)
            with self.assertRaises(RetryDeferred) as caught:
                archive.get(url, lambda raw, _: raw)
            self.assertEqual("ACCESS_DENIED", failure_class(caught.exception))
            self.assertEqual(1, archive.requests)

    def test_nasa_weather_validates_units_and_converts_wind(self):
        import json
        from tempfile import TemporaryDirectory
        from ex_history_archive import HistoryArchive
        from ex_history_environment import nasa_power_at

        values = {"T2M": (5, "C"), "PRECTOTCORR": (1.2, "mm/hour"), "WS10M": (2, "m/s")}
        payload = {
            "geometry": {"coordinates": [-0.1, 51.5, 0]},
            "header": {"time_standard": "UTC", "fill_value": -999},
            "parameters": {key: {"units": value[1]} for key, value in values.items()},
            "properties": {"parameter": {key: {"2025100115": value[0]} for key, value in values.items()}},
        }
        with TemporaryDirectory() as root:
            archive = HistoryArchive(root, 1, fetch=lambda url: json.dumps(payload).encode())
            record = nasa_power_at(archive, (51.5, -0.1), "2025-10-01T15:43:00Z")
        self.assertEqual("RETROSPECTIVE_REANALYSIS", record["kind"])
        self.assertEqual(7.2, record["values"]["wind_speed_10m"])

    def test_scoreboard_queries_once_across_both_queues(self):
        import json
        from tempfile import TemporaryDirectory
        from ex_history_archive import HistoryArchive
        from run_ex_history_scores import collect_scores

        day = "2025-10-01"
        teams = [("home", "Alpha", "2"), ("away", "Beta", "1")]
        payload = {"leagues": [{"slug": "eng.1"}], "events": [{
            "date": day + "T15:00Z", "status": {"type": {"completed": True}},
            "competitions": [{"competitors": [{"homeAway": side, "team": {"displayName": team}, "score": score}
                                               for side, team, score in teams]}]}]}
        target = {"date": day, "league": "en.1", "home": "Alpha", "away": "Beta",
                  "home_goals": 2, "away_goals": 1}
        with TemporaryDirectory() as root:
            archive = HistoryArchive(root, 1, fetch=lambda url: json.dumps(payload).encode())
            result = collect_scores({"historical": [target], "newer": [{**target, "home_goals": 1}]},
                                    "2026-11-24", {}, archive)
        self.assertEqual(1, result["requests"])
        self.assertEqual(1, len(result["queues"]["historical"]["provisional_matches"]))
        self.assertEqual(1, len(result["queues"]["newer"]["conflicts"]))
        self.assertFalse(result["ex_final_allowed"])

    def test_rate_limit_pauses_other_uncached_urls_on_same_host(self):
        import datetime as dt
        from tempfile import TemporaryDirectory
        from urllib.error import HTTPError
        from ex_history_archive import HistoryArchive, RetryDeferred

        now = dt.datetime(2026, 11, 24, tzinfo=dt.timezone.utc)

        def limited(url):
            raise HTTPError(url, 429, "Too Many Requests",
                            {"Retry-After": "Tue, 24 Nov 2026 03:00:00 GMT"}, None)

        with TemporaryDirectory() as root:
            archive = HistoryArchive(root, 4, fetch=limited, clock=lambda: now)
            with self.assertRaises(HTTPError):
                archive.get("https://site.api.espn.com/one", lambda raw, _: raw)
            with self.assertRaises(RetryDeferred) as caught:
                archive.get("https://site.api.espn.com/two", lambda raw, _: raw)
            self.assertEqual("2026-11-24T03:00:00+00:00", caught.exception.checkpoint["retry_after"])
            self.assertEqual(1, archive.requests)

    def test_content_schema_update_retries_only_content_failure(self):
        from tempfile import TemporaryDirectory
        from ex_history_archive import HistoryArchive, RetryDeferred

        url = "https://site.api.espn.com/changed"

        def reject(raw, captured):
            raise ValueError("old parser rejected fixture")

        with TemporaryDirectory() as root:
            archive = HistoryArchive(root, 3, fetch=lambda url: b"payload")
            with self.assertRaisesRegex(ValueError, "old parser"):
                archive.get(url, reject, content_schema="v1")
            with self.assertRaises(RetryDeferred):
                archive.get(url, reject, content_schema="v1")
            result, _ = archive.get(url, lambda raw, _: raw, content_schema="v2")
            self.assertEqual(b"payload", result)
            self.assertEqual(2, archive.requests)

    def test_fixture_context_keeps_minutes_and_venue_on_correct_side(self):
        from ex_historical_features import ProviderHistory

        game = {"event_id": "2", "kickoff_at": "2026-11-20T15:00:00Z",
                "teams": {"home": "4", "away": "9"}, "completed": True}
        source = {"retrieved_at": "2026-11-21T12:00:00Z"}
        detail = {**game, "source": source, "venue": {"id": "20"}, "player_rows": [
            {"team_id": "4", "athlete_id": "8", "provider_minutes": 73, "nominal_regulation_minutes": None}]}
        archive = ProviderHistory(
            [{"team_id": team, "source": source, "fixtures": [game]} for team in ("4", "9")], {"2": detail},
        )
        result = archive.fixture(game["teams"], "2026-11-26T17:00:00Z", "2026-11-25T12:00:00Z")
        self.assertEqual({"8": 73}, result["sides"]["home"]["provider_minutes_14d"])
        self.assertEqual({}, result["sides"]["away"]["provider_minutes_14d"])
        self.assertEqual("2", result["sides"]["home"]["last_observed_venue"]["event_id"])
        self.assertFalse(result["ex_final_allowed"])
        self.assertEqual(0, archive.pregame_coverage([game])["two_calendars"])

    def test_standings_match_competition_season_and_deduplicate_groups(self):
        import json
        from ex_history_rosters import standing_teams

        rows = [{"team": {"id": str(i)}} for i in range(10, 18)]
        payload = {"season": {"year": 2025}, "uid": "s:600~l:725",
                   "children": [{"standings": {"entries": rows}}, {"standings": {"entries": rows[:2]}}]}
        data = json.dumps(payload)
        self.assertEqual(8, len(standing_teams(data, "s:600~l:725", 2025)))
        with self.assertRaises(ValueError):
            standing_teams(data, "s:600~l:3901", 2025)

    def test_alternative_archive_prefers_regulation_final_score(self):
        import json
        from ex_history_alternative_scores import bundesliga_scores

        game = {"leagueShortcut": "bl1", "leagueSeason": 2025, "matchDateTime": "2025-11-06T14:00:00",
                "matchIsFinished": True, "team1": {"teamName": "Alpha"}, "team2": {"teamName": "Beta"},
                "matchResults": [{"resultTypeID": 1, "pointsTeam1": 0, "pointsTeam2": 1},
                                 {"resultTypeID": 2, "pointsTeam1": 2, "pointsTeam2": 1}]}
        rows = bundesliga_scores(json.dumps([game]), 2025, "2026-11-24")
        self.assertEqual((2, 1), (rows[0]["home_goals"], rows[0]["away_goals"]))
        with self.assertRaises(ValueError):
            bundesliga_scores(json.dumps([game]), 2026, "2026-11-24")

    def test_old_transport_pause_updates_without_changing_rate_limit(self):
        import datetime as dt
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from ex_history_archive import HistoryArchive

        now = dt.datetime(2026, 11, 24, 2, tzinfo=dt.timezone.utc)
        url = "https://site.api.espn.com/scoreboard"
        with TemporaryDirectory() as root:
            archive = HistoryArchive(root, 1, fetch=lambda _: b"ok", clock=lambda: now)
            path = Path(root) / "failures" / (archive.digest(url.encode()) + ".json")
            path.parent.mkdir()
            path.write_text(json.dumps({"category": "TRANSPORT", "error": "network reset",
                                        "retry_after": "2026-11-24T02:30:00Z"}))
            self.assertEqual(b"ok", archive.get(url, lambda raw, _: raw)[0])
