"""Synthetic acceptance only. No production registration is installed."""
from copy import deepcopy
from datetime import date, timedelta
import unittest
from unittest.mock import patch

from ex_calibrator_registry import MODEL_VERSION, mapping, validate_registration
from ex_daily_research import daily_analysis
from ex_history_archive import utc
from ex_out_of_sample_audit import audit_out_of_sample


def registration():
    def rows(n, start, prefix):
        for index in range(n):
            day = (start + timedelta(days=index)).isoformat()
            score = 1 if index % 2 else 0
            yield {"fixture_id": f"{prefix}-{index}", "market": "MS1", "competition": "UEL",
                   "predicted_at": day + "T09:00:00Z", "kickoff_at": day + "T19:00:00Z",
                   "settled_at": day + "T21:00:00Z", "outcome": score, "weighted_score": score,
                   "probability": mapping(score, -4, 8), "reference_probability": .6}

    start = "2026-06-01T00:00:00Z"
    approved = "2026-10-01T00:00:00Z"
    records = [*rows(30, date(2026, 3, 1), "training"), *rows(100, date(2026, 6, 1), "held-out")]
    return {"id": "controlled-Ms1-only", "model_version": MODEL_VERSION, "market": "MS1",
            "competitions": ["UEL"], "coefficients": (-4, 8), "frozen_at": start, "approved_at": approved,
            "independent_review": "https://example.org/synthetic-review",
            "holdout": audit_out_of_sample(records, "MS1", start, approved)}


class ProductionFinalTests(unittest.TestCase):
    def test_rejects_unreviewed_version_scope_and_unmatched_mapping(self):
        entry = registration()
        self.assertTrue(validate_registration(entry, "MS1"))
        for changes in ({"model_version": "wrong"}, {"coefficients": (0, 1)},
                        {"competitions": ["UCL"]}, {"independent_review": ""}):
            self.assertFalse(validate_registration({**entry, **changes}, "MS1"))
        altered = deepcopy(entry)
        altered["holdout"]["split"]["test"][0]["reference_probability"] = True
        self.assertFalse(validate_registration(altered, "MS1"))

    def test_real_daily_decision_path_passes_and_blocks_by_gate(self):
        cutoff = utc("2026-11-26T09:00:00Z")
        kickoff = utc("2026-11-26T20:00:00Z")
        stamp = "2026-11-26T08:50:00Z"
        url = "https://site.api.espn.com/test"
        board = {"url": url, "retrieved_at": stamp}
        fixture = {"league": "UEL", "event_id": "controlled", "home": "Alpha", "away": "Beta",
                   "team_ids": {"home": "1001", "away": "1002"}, "date": "2026-11-26",
                   "kickoff_at": kickoff.isoformat(), "fixture_source": url, "fixture_checked_at": stamp}
        common = {"fixture": fixture, "accepted_at": "2026-11-26T08:55:00Z"}
        parts = {name: {"verified": True, "score": .9, "source": "controlled", "timestamp": stamp}
                 for name in ("team_strength", "match_conditions", "external_factors")}
        params = {"board_evidence": board,
                  "cup_evidence": ({(kickoff, "alpha", "beta")}, {"retrieved_at": stamp}),
                  "context_review": {**common, "status": "CONTEXT_CROSS_VERIFIED"},
                  "ingestion_review": {**common, "status": "INGESTED_CROSS_VERIFIED",
                                       "independent_sources_confirmed": 2},
                  "component_review": {**common, "status": "COMPONENTS_CROSS_VERIFIED",
                                       "markets": {"MS1": parts}}}
        quote = {"market": "MS1", "decimal_odds": 1.20, "bookmaker": "Controlled",
                 "observed_at": stamp, "source": "Controlled price"}
        history = {}
        for side, club, league in (("home", "1001", "eng.1"), ("away", "1002", "ita.1")):
            history[club] = []
            for year in (2025, 2026):
                for day in range(1, 11):
                    when = utc(f"{year}-09-{day:02}T10:00:00Z")
                    history[club].append({"kickoff": when, "finished": when + timedelta(hours=2),
                                          "captured_at": when + timedelta(hours=3), "competition": league,
                                          "teams": {side: club, "away" if side == "home" else "home": "other"},
                                          "score": (2, 1)})

        def run(**changes):
            inputs = {**params, "quotes": [quote], "by_team": history, **changes}
            return daily_analysis(fixture, None, None, cutoff, **inputs)

        self.assertIn("exg:uncalibrated", run()["auto_control_by_market"]["MS1"]["issues"])
        with patch.dict("ex_decision._APPROVED_CALIBRATORS", {"MS1": registration()}, clear=True):
            self.assertEqual(["MS1"], run()["final_markets"])
            early_quote = {**quote, "observed_at": (kickoff - timedelta(hours=49)).isoformat()}
            self.assertIn("odds_lock:blocked",
                          run(quotes=[early_quote])["auto_control_by_market"]["MS1"]["issues"])
            early = kickoff - timedelta(hours=60)
            early_stamp = (early - timedelta(minutes=10)).isoformat()
            early_fixture = {**fixture, "fixture_checked_at": early_stamp}
            early_inputs = {
                **params,
                "board_evidence": {**board, "retrieved_at": early_stamp},
                "cup_evidence": ({(kickoff, "alpha", "beta")}, {"retrieved_at": early_stamp}),
            }
            for review in ("context_review", "ingestion_review", "component_review"):
                early_inputs[review] = {**params[review], "fixture": early_fixture,
                                        "accepted_at": (early - timedelta(minutes=5)).isoformat()}
            research = daily_analysis(early_fixture, None, None, early, by_team=history,
                                      quotes=[{**quote, "observed_at": early_stamp}], **early_inputs)
            self.assertIsNotNone(research["domestic_research"]["baseline"])
            self.assertTrue(research["tur2"])
            self.assertFalse(research["live_evidence_window"])
            self.assertIn("live_evidence:48h_pending", research["auto_control_by_market"]["MS1"]["issues"])
            self.assertIsNone(research["markets"]["markets"]["MS1"]["ex_g"]["probability"])
            self.assertEqual([], research["final_markets"])

            for changes, reason in (({"by_team": {}}, "historical_samples:incomplete"),
                                    ({"cup_evidence": None}, "second_source:unverified"),
                                    ({"context_review": None}, "context:unverified")):
                result = run(**changes)["auto_control_by_market"]["MS1"]
                self.assertEqual("BLOCKED", result["status"])
                self.assertIn(reason, result["issues"])
            with patch("ex_daily_research.cross_league_baseline",
                       side_effect=[{"baseline": None}, {"baseline": None, "other": 1}]):
                self.assertIn("tur2:recompute_mismatch", run()["auto_control_by_market"]["MS1"]["issues"])
            self.assertEqual("PASS", run(quotes=[{**quote, "decimal_odds": 1.19}])["auto_control_by_market"]["MS1"]["status"])
