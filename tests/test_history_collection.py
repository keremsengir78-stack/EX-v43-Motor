import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from ex_history_archive import BudgetExhausted, HistoryArchive, utc
from ex_history_sources import match_detail, regulation_minutes, schedule, uefa_news

URL = "https://site.api.espn.com/example"


class HistoryCollectionTests(unittest.TestCase):
    def test_budget_resume_and_source_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def fetch(url):
                calls.append(url)
                return url.encode()
            parse = lambda raw, _: raw.decode()
            first = HistoryArchive(directory, 1, fetch)
            first.get(URL, parse)
            with self.assertRaises(BudgetExhausted):
                first.get(URL + "/next", parse)
            resumed = HistoryArchive(directory, 1, fetch)
            _, meta = resumed.get(URL, parse)
            resumed.get(URL + "/next", parse)
            self.assertEqual([URL, URL + "/next"], calls)
            (Path(directory) / "raw" / meta["sha256"]).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "integrity"):
                resumed.get(URL, parse)

    def test_prematch_snapshot_survives_later_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            past = utc("2026-11-22T12:00:00Z")
            later = utc("2026-11-24T12:00:00Z")
            archive = HistoryArchive(directory, 1, lambda _: b"later", clock=lambda: later)
            archive.import_capture(URL, b"past", past, archive.digest(b"past"))
            archive.get(URL, lambda raw, _: raw, max_age=dt.timedelta(hours=6))
            raw, when, _ = archive.prior_capture(URL, utc("2026-11-23T12:00:00Z"))
            self.assertEqual((b"past", past), (raw, when))

    def test_schedule_and_summary_require_same_fixture_identity(self):
        stamp = "2026-11-20T12:00:00Z"
        game = {"id": "1", "date": stamp, "competitors": [
            {"homeAway": "home", "team": {"id": "4"}}, {"homeAway": "away", "team": {"id": "7"}},
        ], "status": {"type": {"state": "post", "completed": True}}}
        payload = {"team": {"id": "4"}, "requestedSeason": {"year": 2026},
                   "events": [{"id": "1", "date": stamp, "competitions": [game], "league": {"slug": "eng.1"}}]}
        event = schedule(json.dumps(payload).encode(), "4", 2026)["1"]
        final = {"header": {"id": "1", "competitions": [game]}}
        self.assertTrue(match_detail(json.dumps(final).encode(), utc(stamp), event)["completed"])
        with self.assertRaisesRegex(ValueError, "identity"):
            match_detail(json.dumps(final).encode(), utc(stamp), {**event, "event_id": "2"})

    def test_substitution_and_dismissal_minutes(self):
        player = {"starter": True, "subbedIn": False, "subbedOut": True,
                  "plays": [{"substitution": True, "clock": {"displayValue": "64'"}}],
                  "stats": [{"name": "redCards", "value": 0}]}
        self.assertEqual(64, regulation_minutes(player))
        self.assertIsNone(regulation_minutes({**player, "plays": []}))
        player["stats"][0]["value"] = 1
        self.assertIsNone(regulation_minutes(player))

    def test_uefa_report_requires_capture_strictly_before_kickoff(self):
        raw = (b'<h4><a href="/match/13--h-vs-a">H vs A</a></h4>'
               b'<p>H: XI<br>Out: Player<br>Doubtful: None</p>'
               b'<p>A: XI<br>Out: None<br>Doubtful: None</p>')
        target = {"uefa_match_id": "13", "normalized_teams": ["h", "a"],
                  "kickoff_at": "2026-11-24T20:00:00Z"}
        self.assertTrue(uefa_news(raw, utc("2026-11-24T19:00:00Z"), [target])[0]["prematch_eligible"])
        self.assertIsNone(uefa_news(raw, utc(target["kickoff_at"]), [target])[0]["reported_availability"])

    def test_duplicate_athlete_is_excluded_without_losing_fixture(self):
        stamp = "2026-11-20T12:00:00Z"
        game = {"id": "1", "date": stamp, "competitors": [
            {"homeAway": "home", "team": {"id": "4"}}, {"homeAway": "away", "team": {"id": "7"}},
        ], "status": {"type": {"state": "post", "completed": True}}}
        duplicate = {"athlete": {"id": "13"}}
        valid = {"athlete": {"id": "14"}, "stats": [{"name": "minutesPlayed", "value": 90}]}
        summary = {"header": {"id": "1", "competitions": [game]}, "rosters": [
            {"team": {"id": "4"}, "homeAway": "home", "roster": [duplicate, valid]},
            {"team": {"id": "7"}, "homeAway": "away", "roster": [duplicate]},
        ]}
        event = {"event_id": "1", "kickoff_at": stamp, "teams": {"home": "4", "away": "7"}}
        result = match_detail(json.dumps(summary).encode(), utc(stamp), event)
        self.assertTrue(result["completed"])
        self.assertEqual(["13"], result["roster_identity_conflicts"])
        self.assertEqual(["14"], [row["athlete_id"] for row in result["player_rows"]])
        self.assertEqual(90, result["player_rows"][0]["provider_minutes"])
