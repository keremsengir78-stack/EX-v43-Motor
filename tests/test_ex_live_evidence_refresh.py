import datetime as dt
import json
from unittest import TestCase
from unittest.mock import Mock

from ex_history_archive import utc
from run_ex_live_evidence_refresh import review_capture


class LiveEvidenceRefreshTests(TestCase):
    def test_requires_both_captures_inside_live_window_and_before_kickoff(self):
        kickoff = utc("2026-11-29T18:00:00Z")
        competition = {"id": "1", "date": kickoff.isoformat(),
                       "competitors": [{"homeAway": side, "id": identifier, "team": {"id": identifier}}
                                       for side, identifier in (("home", "10"), ("away", "20"))],
                       "status": {"type": {"state": "pre"}}}
        board = {"leagues": [{"slug": "eng.1"}],
                 "events": [{**competition, "competitions": [competition]}]}
        detail = {"header": {"id": "1", "competitions": [competition]},
                  "rosters": [{"team": {"id": "10"}}]}
        fixture = {"event_id": "1", "league": "en.1",
                   "kickoff_at": kickoff.isoformat(), "team_ids": {"home": "10", "away": "20"}}
        manifest = {"day": "2026-11-29", "reports": {"en.1": {"board": {"url": "board", "retrieved_at": kickoff.isoformat()},
                    "records": [{"event_id": "1", "source": {"url": "summary", "retrieved_at": kickoff.isoformat()}}]}}}
        start = kickoff - dt.timedelta(hours=48)
        for captures, cutoff, expected in (((start, start), start + dt.timedelta(seconds=1), 1),
                ((start, start - dt.timedelta(seconds=1)), start + dt.timedelta(seconds=1), 0),
                ((start, start), kickoff, 0)):
            cache = Mock()
            cache._load.side_effect = [(json.dumps(x), when) for x, when in zip((board, detail), captures)]
            rows, issues = review_capture(manifest, cache, {"1": fixture}, cutoff)
            self.assertEqual(expected, len(rows))
            self.assertEqual(1 - expected, len(issues))
            if rows:
                self.assertEqual(0, rows[0]["player_roster_entries_observed"])
                self.assertFalse(rows[0]["ex_final_allowed"])
