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

    def test_four_independently_calibrated_markets_still_need_registered_pup(self):
        def mock_g(market, weighted):
            return {"status": "EX_G_AVAILABLE", "market": market, "probability": .6}

        with patch("ex_decision.ex_g_from_evidence", side_effect=mock_g):
            result = assess_markets({})
        self.assertEqual(list(MARKETS), result["pup"]["markets_checked"])
        self.assertEqual(["pup:approved_executor_unavailable"], result["pup"]["issues"])
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
