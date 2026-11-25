import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from unittest.mock import patch

from ex_decision import MARKETS, assess_markets
from ex_espn_provider import ESPN_LEAGUES
from ex_history_archive import HistoryArchive, utc
from ex_live_data import LEAGUES
from ex_prospective_power import plan, verdict
from run_ex_official_minutes_batch import normalize
from run_ex_prematch_archive import collect_registered
from run_ex_prospective_pipeline import settle
from run_ex_source_audit import audit


class ProspectiveOperationsTests(unittest.TestCase):
    def test_registered_capture_covers_catalog_and_isolates_unavailable_sources(self):
        def collect(_, league, day, limit):
            if league == "az.1":
                raise OSError("unsupported feed")
            return {"eligible": 0, "records": []}

        with TemporaryDirectory() as root, patch("run_ex_prematch_archive.collect", side_effect=collect):
            result = collect_registered(HistoryArchive(root, 0), utc("2026-11-25T00:00:00Z").date(), 5)
        self.assertTrue(set(LEAGUES).issubset(result["registered_leagues"]))
        self.assertEqual(len(ESPN_LEAGUES) - 1, len(result["reports"]))
        self.assertEqual("az.1", result["errors"][0]["league"])

    def test_four_independently_calibrated_markets_do_not_implicitly_run_pup(self):
        def mock_g(market, weighted):
            return {"status": "EX_G_AVAILABLE", "market": market, "probability": .6}

        with patch("ex_decision.ex_g_from_evidence", side_effect=mock_g):
            result = assess_markets({})
        self.assertEqual(list(MARKETS), result["pup"]["markets_checked"])
        self.assertEqual("NOT_REQUESTED", result["pup"]["status"])
        self.assertFalse(result["pup_allowed"])

    def test_power_design_varies_with_effect_size_and_adjusts_family_error(self):
        pilot = [-.005, -.020, -.035, .005]
        first = plan(pilot, .01, .05, .8, 10)
        second = plan(pilot, .02, .05, .8, 10)
        self.assertGreater(first["required_weeks"], second["required_weeks"])
        self.assertEqual(.005, first["per_test_alpha"])
        self.assertFalse(verdict([-.02], first)["research_supported"])
        with self.assertRaises(ValueError):
            plan([-.01, -.01], .01, .05, .8, 10)

    def test_two_provider_names_do_not_prove_independence(self):
        row = {"league": "de.1", "date": "2026-11-20", "home": "A", "away": "B",
               "home_goals": 1, "away_goals": 0}
        ledger = {"queues": {"newer": {"provisional_matches": [row]}},
                  "alternative_bundesliga": {"queues": {"newer": {"verified": [row]}}}}
        result = audit(ledger)
        self.assertEqual({"UPSTREAM_LINEAGE_UNPROVEN": 1}, result["counts"])

    def test_official_batch_retains_valid_matches_when_wrong_host_is_rejected(self):
        row = json.loads(Path("research/ucl/domestic-minutes-pilot.json").read_text())
        result = normalize([row, {**row, "source": "https://unrelated.example/"}])
        self.assertEqual(1, len(result["minutes"]))
        self.assertEqual(1, len(result["errors"]))

    def test_settlement_requires_artifact_before_kickoff(self):
        row = {"event_id": "17", "kickoff": "2026-11-25T19:00:00Z",
               "forecast_at": "2026-11-25T18:00:00Z", "kind": "PROSPECTIVE_VENUE5_RESEARCH"}
        with TemporaryDirectory() as root:
            archive = HistoryArchive(root, 0, clock=lambda: utc("2026-11-25T18:30:00Z"))
            outcomes, provisional, pending = settle([row], archive, utc("2026-11-25T18:01:00Z"), [])
            self.assertEqual(([], [], [{"event_id": "17", "reason": "AWAITING_FULL_TIME"}]),
                             (outcomes, provisional, pending))
            with self.assertRaises(ValueError):
                settle([row], archive, utc(row["kickoff"]), [])

    def test_combining_weeks_keeps_earliest_sealed_forecast(self):
        from run_ex_prospective_pipeline import combine_forecasts
        row = {"event_id": "17", "kickoff": "2026-11-25T19:00:00Z", "league": "de.1",
               "teams": {"home": "1", "away": "2"}, "forecast_at": "2026-11-25T18:00:00Z"}
        later = {**row, "forecast_at": "2026-11-25T18:20:00Z"}
        result = combine_forecasts([(utc("2026-11-25T18:25:00Z"), [later]),
                                    (utc("2026-11-25T18:10:00Z"), [row])])
        self.assertEqual([row["forecast_at"]], [item["forecast_at"] for item in result])

    def test_czech_report_tokens_parse_starters_and_changes(self):
        from run_ex_official_minutes_batch import parse_parenthetical_lineup

        starters, changes = parse_parenthetical_lineup("A (46. K) - B, C (71. L)")
        self.assertEqual(["A", "B", "C"], starters)
        self.assertEqual([(46, "A", "K"), (71, "C", "L")], changes)
        with self.assertRaises(ValueError):
            parse_parenthetical_lineup("A (unknown)")

    def test_settlement_separates_one_source_from_official_result(self):
        import json
        kickoff = "2026-11-25T19:00:00Z"
        row = {"event_id": "17", "kickoff": kickoff, "league": "de.1", "season": 2026,
               "teams": {"home": "1", "away": "2"}, "names": {"home": "A", "away": "B"},
               "forecast_at": "2026-11-25T18:00:00Z", "kind": "PROSPECTIVE_VENUE5_RESEARCH"}
        match = {"id": "17", "date": kickoff, "status": {"type": {"name": "STATUS_FULL_TIME",
                 "state": "post", "completed": True}}, "competitors": [
            {"homeAway": side, "team": {"id": club}, "score": score}
            for (side, club), score in zip(row["teams"].items(), [2, 1], strict=True)]}
        raw = json.dumps({"header": {"id": "17", "competitions": [match]}}).encode()
        review = {"league": "de.1", "date": "2026-11-25", "home": "A", "away": "B", "score": [2, 1],
                  "source": "https://www.bundesliga.com/en/bundesliga/matchday/2026-2027/1",
                  "verified_at": "2026-11-25T22:00:00Z", "scope": "REVIEWED_OFFICIAL_RESULT"}
        seal = utc("2026-11-25T18:01:00Z")
        with TemporaryDirectory() as root:
            archive = HistoryArchive(root, 1, fetch=lambda url: raw, clock=lambda: utc("2026-11-25T22:00:00Z"))
            self.assertEqual(1, len(settle([row], archive, seal, [])[1]))
            verified, _, _ = settle([row], archive, seal, [review])
            self.assertEqual(1, len(verified))
            self.assertEqual(1, verified[0]["labels"]["KG_VAR"])
            self.assertEqual(1, archive.requests)

    def test_receipt_accepts_flat_or_nested_but_not_ambiguous_archive(self):
        from run_ex_prospective_pipeline import read_forecast_pack

        with TemporaryDirectory() as root:
            base = Path(root)
            receipt = base / "receipt.json"
            receipt.write_text(json.dumps({"name": "ex-prospective-forecasts",
                                           "created_at": "2026-11-25T10:00:00Z"}))
            flat = base / "forecasts.jsonl"
            flat.write_text('{"event_id":"17"}\n')
            self.assertEqual("17", read_forecast_pack(receipt)[1][0]["event_id"])
            nested = base / "forecasts/forecasts.jsonl"
            nested.parent.mkdir()
            nested.write_text(flat.read_text())
            with self.assertRaises(ValueError):
                read_forecast_pack(receipt)
            flat.unlink()
            self.assertEqual("17", read_forecast_pack(receipt)[1][0]["event_id"])


    def test_fixed_components_score_only_complete_prematch_evidence(self):
        from run_ex_prospective_validation import evaluate

        evidence = {name: {"score": score, "verified": True, "source": "verified archive",
                           "timestamp": "2026-11-24T20:00:00Z"}
                    for name, score in (("team_strength", .6), ("match_conditions", .8),
                                        ("external_factors", .1))}
        frozen = dict(frozen_at="2026-11-24T12:00:00Z",
                      original_last_kickoff="2026-11-23T19:00:00Z", original_ids=[],
                      coefficients={"KG_VAR": [0, 1], "2.5_UST": [0, 1]})
        row = dict(event_id="1", forecast_at="2026-11-25T17:00:00Z", kickoff="2026-11-25T18:00:00Z",
                   finished="2026-11-25T20:00:00Z", labels=dict.fromkeys(MARKETS, 1),
                   short=dict.fromkeys(MARKETS, .5), components={"KG_VAR": evidence})
        result = evaluate(frozen, [row])["markets"]
        candidate = result["KG_VAR"]["fixed_components_research"]
        self.assertAlmostEqual((.56 - 1) ** 2, candidate["candidate_brier"])
        self.assertFalse(candidate["supported"])
        self.assertEqual(0, result["2.5_UST"]["fixed_components_research"]["n"])
        evidence["external_factors"]["timestamp"] = row["kickoff"]
        self.assertEqual(0, evaluate(frozen, [row])["markets"]["KG_VAR"]["fixed_components_research"]["n"])

    def test_upl_calendar_rejects_youth_and_resolves_local_time(self):
        from ex_official_calendar import calendar_fixtures

        def fixture(match_id, league, marker):
            return f'''<div class="tour-match u21">
                <div class="match-tournament"><!-- -->{league}</div>
                <div class="team first-team"><div class="logo"></div>Shakhtar</div>
                <a href="/en/report/view/{match_id}">{marker}</a>
                <div class="team second-team"><div class="logo"></div>Dynamo</div>'''

        page = ('<div class="tour-date">Wed, 25.11.2026</div>' + fixture(1, "UPL", "20:00")
                + fixture(2, "UPL2", "19:00") + fixture(3, "UPL", "1 : 0"))
        clock = utc("2026-11-25T17:00:00Z")
        evidence = {"captured_at": clock.isoformat(), "final_url": "https://upl.ua/en/tournaments/games"}
        match, = calendar_fixtures("ua.1", page, evidence, clock.date())
        self.assertEqual("1", match["source_match_id"])
        self.assertEqual("https://upl.ua/en/report/view/1", match["official_match_url"])
        self.assertEqual("2026-11-25T18:00:00+00:00", match["kickoff_at"])
        self.assertEqual({"home": "Shakhtar", "away": "Dynamo"}, match["names"])
        self.assertIsNone(match["espn_event_id"])
        self.assertIsNone(match["odds_evidence"])
        evidence["captured_at"] = "2026-11-25T18:00:00Z"
        self.assertEqual([], calendar_fixtures("ua.1", page, evidence, clock.date()))


    def test_preregistered_cohort_selection_preserves_only_eligible_settlements(self):
        from run_ex_prospective_pipeline import select_evaluation_rows

        model = {"original_ids": ["old"], "original_last_kickoff": "2026-11-22T10:00:00Z",
                 "frozen_at": "2026-11-23T10:00:00Z"}
        design = {"registered_at": "2026-11-24T10:00:00Z", "holdout_start": "2026-11-25T00:00:00Z",
                  "holdout_end": "2026-12-01T00:00:00Z"}
        valid = {"event_id": "new", "forecast_at": "2026-11-25T02:00:00Z", "kickoff": "2026-11-25T19:00:00Z"}
        rows = [valid, {**valid, "event_id": "old"}, {**valid, "event_id": "before",
                "forecast_at": "2026-11-24T19:00:00Z"}, {**valid, "event_id": "after",
                "kickoff": design["holdout_end"]}]
        self.assertEqual([valid], select_evaluation_rows(model, rows, design))

    def test_laliga_audit_uses_only_published_full_time_scores(self):
        from run_ex_laliga_bulk import LALIGA, extract

        url = f"{LALIGA}/2026-27/gameweek-4"
        match = {"id": 1, "date": "2026-09-06T14:15:00+00:00", "home_score": 0, "away_score": 5,
                 "home_team": {"slug": "valencia-cf"}, "away_team": {"slug": "fc-barcelona"},
                 "status": "FullTime"}
        props = {"competition": "primera-division", "isGameweekPage": True, "gameweek": {"week": 4},
                 "canonical": url, "matches": [match, {**match, "id": 2, "status": "InPlay"}]}
        state = json.dumps({"props": {"pageProps": props}})
        result, skipped = extract(f'<script id="__NEXT_DATA__">{state}</script>', url,
                                  "2026-09-07T10:00:00+00:00")
        self.assertEqual(set(), skipped)
        self.assertEqual([0, 5], result[0]["official_score"])
        self.assertEqual(1, len(result))
        ledger = {"queues": {"newer": {"provisional_matches": [
            {**result[0], "season": "2026-27", "home_goals": 0, "away_goals": 5}]}}}
        audited = audit(ledger, {"fixtures": result})
        self.assertEqual({"OFFICIAL_RESULT_CORROBORATION_ONLY": 1}, audited["counts"])
        self.assertEqual("2026-27", audited["league_season_counts"][0]["season"])
        self.assertFalse(audited["categories"]["OFFICIAL_RESULT_CORROBORATION_ONLY"][0]["upstream_lineage_certified"])

    def test_pfl_binds_protocol_to_league_match_and_local_kickoff(self):
        from run_ex_pfl_discovery import match_plan, roster_context

        clubs = [{"id": 8, "title": "Sabah"}, {"id": 6, "title": "Zirə"}]
        fixture = {"id": 6807, "start_date": "05/09/2026 18:30", "status": 0,
                   "club_1": clubs[0], "club_2": clubs[1],
                   "protocol_src": "https://pfl.az/storage/games/files/6a9c4a2d0c875_1788627501.pdf"}
        payload = {"data": [{"league": {"id": 52}, "games": [fixture]}]}
        evidence = {"captured_at": "2026-09-05T13:00:00Z"}
        result, = match_plan(payload, 52, evidence)
        self.assertEqual(6807, result["official_match_id"])
        self.assertEqual("2026-09-05T14:30:00+00:00", result["kickoff_at"])
        self.assertEqual({"home": 8, "away": 6}, result["source_team_ids"])
        with self.assertRaises(ValueError):
            list(match_plan(payload, 47, evidence))
        detail = {**fixture, "league": {"id": 52}, "club_1": {**clubs[0], "players": [{"id": 10}]}}
        self.assertEqual({"home": 1, "away": 0}, roster_context(result, detail, evidence)["counts"])
        with self.assertRaises(ValueError):
            roster_context(result, detail, {"captured_at": result["kickoff_at"]})
        with self.assertRaises(ValueError):
            roster_context(result, {**detail, "club_2": clubs[0]}, evidence)

    def test_league_coverage_keeps_eerste_divisie_inactive(self):
        from run_ex_league_coverage import coverage

        result = coverage({"leagues": {}})
        row = result["registered_leagues"]["nl.2"]
        self.assertFalse(row["main_ingestion"])
        self.assertIsNone(row["espn_adapter"])
        self.assertEqual([], row["history_seed_seasons"])
        self.assertFalse(result["ex_final_allowed"])

    def test_alternate_fixture_binds_only_the_exact_archived_espn_sides(self):
        from run_ex_prospective_pipeline import bind_espn_context

        day = utc("2026-11-27T00:00:00Z").date()
        clock = utc("2026-11-27T12:00:00Z")
        kickoff = "2026-11-27T19:00:00Z"
        state = {"type": {"state": "pre"}}
        names = {"home": "Sabah", "away": "Zirə"}
        competition = {"id": "6807", "date": kickoff, "status": state,
                       "competitors": [{"homeAway": side, "team": {"id": str(i), "displayName": name}}
                                       for i, (side, name) in enumerate(names.items(), 1)]}
        board = {"leagues": [{"slug": "aze.1"}], "events": [
            {"id": "6807", "date": kickoff, "status": state, "competitions": [competition]}]}
        detail = {"header": {"id": "6807", "competitions": [competition]}, "rosters": [{"id": "1"}]}
        spec = {"competition_verified": True, "kickoff_at": kickoff, "names": names}
        reports = {"az.1": {"board": {}, "records": [{"event_id": "6807", "source": {}}]}}
        reversed_fixture = {**spec, "names": {"home": names["away"], "away": names["home"]}}
        with TemporaryDirectory() as root, patch.object(HistoryArchive, "_load", side_effect=[
                (json.dumps(board).encode(), clock), (json.dumps(detail).encode(), clock)]):
            bind_espn_context({"az.1": [spec, reversed_fixture]}, reports, root, day)
        self.assertEqual("6807", spec["espn_event_id"])
        self.assertEqual("PREGAME_ROSTER_PAYLOAD", spec["lineup_evidence"]["scope"])
        self.assertIsNone(spec["odds_evidence"])
        self.assertNotIn("espn_event_id", reversed_fixture)
