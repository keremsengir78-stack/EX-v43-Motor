import datetime as dt
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ex_decision import MARKETS
from ex_history_archive import HistoryArchive, utc
from ex_history_sources import ESPN
from ex_leagues import APPROVED_LEAGUES
from run_ex_prematch_archive import collect_registered, seed_recent_pregame
from run_ex_prospective_pipeline import OFFICIAL_RESULT_HOSTS, archive_history, forecast_rows, jsonl, settle
from run_ex_weekly_capacity import observed_coverage


class ArchiveChainTests(unittest.TestCase):
    def test_all_approved_competitions_capture_and_replay_paired_results(self):
        now = utc("2026-11-25T12:00:00Z")
        kickoff = utc("2026-11-25T20:00:00Z")
        finished = kickoff + dt.timedelta(hours=2)
        teams = {"home": "11", "away": "12"}
        payloads, final_payloads, facts, fixtures, reviews = {}, {}, [], {}, []
        for index, (league, (_, slug, _, _)) in enumerate(APPROVED_LEAGUES.items(), 200):
            event = str(index)
            start = kickoff.isoformat()
            competitors = [{"homeAway": side, "team": {"id": club, "displayName": side}, "score": score}
                           for (side, club), score in zip(teams.items(), (2, 1), strict=True)]
            match = {"id": event, "date": start, "competitors": competitors,
                     "status": {"type": {"state": "pre", "completed": False}}}
            board = {"leagues": [{"slug": slug}], "events": [{**match, "season": {"year": 2026},
                                                              "competitions": [match]}]}
            payloads[f"{ESPN}/{slug}/scoreboard?dates=20261125"] = json.dumps(board).encode()
            url = f"{ESPN}/{slug}/summary?event={event}"
            payloads[url] = json.dumps({"header": {"id": event, "competitions": [match]}}).encode()
            final = {**match, "status": {"type": {"state": "post", "name": "STATUS_FULL_TIME", "completed": True}}}
            final_payloads[url] = json.dumps({"header": {"id": event, "competitions": [final]}}).encode()
            fixtures[event] = {"league": league, "teams": teams, "kickoff": start}
            reviews.append({"league": league, "date": "2026-11-25", "home": "home", "away": "away",
                            "source": f"https://{min(OFFICIAL_RESULT_HOSTS[league])}/results",
                            "verified_at": finished.isoformat(), "score": [2, 1],
                            "scope": "REVIEWED_OFFICIAL_RESULT"})
            for n in range(1, 6):
                start_at = kickoff - dt.timedelta(days=n * 7)
                for side, club in teams.items():
                    facts.append({"event_id": f"{index}{n}{club}", "competition": slug, "season": 2026,
                                  "teams": {side: club, "away" if side == "home" else "home": "99"},
                                  "kickoff": start_at, "finished": start_at + dt.timedelta(hours=2),
                                  "captured_at": start_at + dt.timedelta(hours=3), "score": (2, 1)})

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            pre = root / "packs/1"
            archive = HistoryArchive(pre / "pregame-cache", len(payloads),
                                     fetch=lambda url: payloads[url], clock=lambda: now)
            from run_ex_prematch_archive import LIVE_WINDOW, RESEARCH_WINDOW, prematch_fixtures
            slug = APPROVED_LEAGUES["de.2"][1]
            raw = payloads[f"{ESPN}/{slug}/scoreboard?dates=20261125"]
            for hours, live, research in ((48, True, True), (49, False, True),
                                           (96, False, True), (97, False, False)):
                stamp = kickoff - dt.timedelta(hours=hours)
                self.assertEqual(live, bool(prematch_fixtures(raw, stamp, kickoff.date(), slug, LIVE_WINDOW)))
                self.assertEqual(research, bool(prematch_fixtures(raw, stamp, kickoff.date(), slug, RESEARCH_WINDOW)))
            manifest = collect_registered(archive, kickoff.date(), 25, APPROVED_LEAGUES)
            as_of = now + dt.timedelta(minutes=1)
            archive.clock = lambda: as_of
            daily = []
            forecasts, skipped = forecast_rows(manifest, archive, facts, as_of, daily=daily)
            self.assertEqual(set(APPROVED_LEAGUES), {row["league"] for row in forecasts})
            self.assertEqual([], skipped)
            self.assertTrue(all(row["tur2"] and not row["ex_final_allowed"] for row in daily))
            sealed = as_of + dt.timedelta(minutes=1)
            (pre / "capture.json").write_text(json.dumps(manifest))
            (pre / "forecasts.jsonl").write_bytes(jsonl(forecasts))
            (pre / "receipt.json").write_text(json.dumps({"name": "ex-prospective-forecasts",
                                                         "created_at": sealed.isoformat()}))
            prior = HistoryArchive(root / "seeded", 0, clock=lambda: sealed + dt.timedelta(minutes=1))
            self.assertEqual(len(payloads), seed_recent_pregame(root / "packs", prior, kickoff.date()))
            cached = collect_registered(prior, kickoff.date(), 25, APPROVED_LEAGUES)
            self.assertEqual([], cached["errors"])
            self.assertEqual(0, prior.requests)
            self.assertEqual(len(payloads), prior.cache_hits)
            post = root / "settled/2"
            result_archive = HistoryArchive(post / "settlement-cache", len(fixtures),
                                            fetch=lambda url: final_payloads[url], clock=lambda: finished)
            outcomes, provisional, pending = settle(forecasts, result_archive, sealed, reviews)
            self.assertEqual(len(APPROVED_LEAGUES), len(outcomes))
            self.assertEqual(([], []), (provisional, pending))
            (post / "settlement").mkdir()
            (post / "settlement/outcomes.jsonl").write_bytes(jsonl(outcomes))
            after = finished + dt.timedelta(minutes=2)
            (post / "receipt.json").write_text(json.dumps({"created_at": after.isoformat()}))
            archived = {}
            _, reused = archive_history(root / "settled", [], after + dt.timedelta(minutes=1),
                                        verified_outcomes=archived)
            self.assertEqual(len(APPROVED_LEAGUES), reused)
            self.assertEqual(set(fixtures), set(archived))
            coverage, performance = observed_coverage(fixtures, root / "packs", root / "settled")
            self.assertTrue(all(row["independently_settled_venue5"] == 1 for row in coverage.values()))
            self.assertEqual(len(APPROVED_LEAGUES), performance["matched"])
            self.assertEqual(set(MARKETS), set(performance["venue5_brier"]))
            self.assertFalse(performance["production_allowed"])

            corrupt = {**outcomes[0], "score": [9, 9]}
            (post / "settlement/outcomes.jsonl").write_bytes(jsonl([corrupt, *outcomes[1:]]))
            cutoff = after + dt.timedelta(minutes=1)
            with self.assertRaisesRegex(ValueError, "Unverified official settlement evidence"):
                archive_history(root / "settled", [], cutoff)
            second = root / "settled/3"
            from shutil import copytree

            copytree(post, second)
            (post / "settlement/outcomes.jsonl").write_bytes(jsonl(outcomes))
            conflicts, verified = set(), {}
            remaining, count = archive_history(root / "settled", [], cutoff, conflicts=conflicts,
                                               verified_outcomes=verified)
            self.assertNotIn(corrupt["event_id"], verified)
            self.assertEqual(len(APPROVED_LEAGUES) - 1, len(verified))
            self.assertEqual({corrupt["event_id"]}, conflicts)
            self.assertEqual(len(APPROVED_LEAGUES) - 1, count)
            self.assertEqual(len(APPROVED_LEAGUES) - 1, len(remaining))
