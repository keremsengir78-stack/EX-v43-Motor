import json
import unittest

from ex_cup_team_history import schedule_facts
from ex_history_archive import utc
from ex_leagues import APPROVED_LEAGUES, season_bounds


class CupTeamHistoryTests(unittest.TestCase):
    def test_requires_exact_identity_and_completed_pre_cutoff_score(self):
        date = "2026-10-01T17:00:00Z"
        event = {"id": "900", "date": date, "season": {"year": 2026}, "league": {"slug": "sco.1"},
                 "competitions": [{"id": "900", "date": date,
                    "status": {"type": {"name": "STATUS_FULL_TIME", "completed": True}},
                    "competitors": [{"homeAway": side, "team": {"id": club}, "score": {"value": score}}
                                    for side, club, score in (("home", "262", 2), ("away", "256", 1))]}]}
        payload = {"team": {"id": "262"}, "requestedSeason": {"year": 2026}, "events": [event]}
        cutoff = utc("2026-11-26T06:00:00Z")
        facts = schedule_facts(json.dumps(payload), cutoff, "262", "sco.1", 2026)
        self.assertEqual((2, 1), facts[0]["score"])
        self.assertEqual(cutoff, facts[0]["finished"])
        self.assertEqual([], schedule_facts(json.dumps(payload), utc(date), "262", "sco.1", 2026))
        with self.assertRaises(ValueError):
            schedule_facts(json.dumps(payload), cutoff, "999", "sco.1", 2026)

    def test_support_sources_do_not_expand_daily_scope(self):
        now = utc("2026-11-26T06:00:00Z").date()
        self.assertNotIn("se.1", APPROVED_LEAGUES)
        self.assertEqual(1, season_bounds("se.1", now)[0].month)
        self.assertEqual(7, season_bounds("dk.1", now)[0].month)
