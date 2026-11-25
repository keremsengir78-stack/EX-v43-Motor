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
