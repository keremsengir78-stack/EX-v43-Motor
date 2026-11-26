from datetime import date
import json
import unittest

from ex_cup_team_history import csv_facts, schedule_facts
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


    def test_csv_requires_reviewed_anchor_and_exact_club_alias(self):
        data = ("Country,League,Season,Date,Home,Away,HG,AG\n"
                "Romania,Superliga,2026/2027,22/11/2026,UTA Arad,Univ. Craiova,2,6\n"
                "Romania,Superliga,2025/2026,24/11/2025,UTA Arad,U Craiova 1948,2,1\n")
        stamp = utc("2026-11-26T06:00:00Z")
        rows = csv_facts(data.encode(), stamp, "ro.1", stamp.date(), ["8089"])
        self.assertEqual("8089", rows[0]["teams"]["away"])
        self.assertEqual("football-data:rou.1:U Craiova 1948", rows[1]["teams"]["away"])
        self.assertEqual(stamp, rows[0]["captured_at"])
        with self.assertRaisesRegex(ValueError, "anchor missing"):
            csv_facts(data.replace(",2,6", ",2,5").encode(), stamp, "ro.1", stamp.date(), ["8089"])

    def test_previous_window_keeps_competition_and_venue_after_promotion(self):
        from ex_engine import weighted_form

        cutoff = date(2026, 11, 26)
        start, prior = season_bounds("no.1", cutoff)
        current = [dict(date=date(2026, 10, day), league="no.1", home=str(day), away="987", hg=1, ag=2)
                   for day in range(1, 11)]
        previous = dict(date=date(2025, 10, 1), league="nor.2", home="other", away="987", hg=1, ag=3)
        value, audit = weighted_form([*current, previous], "987", "away", cutoff, "no.1", start, prior)
        self.assertIsNone(value)
        self.assertEqual([5, 10, 10, 0], audit["counts"])
