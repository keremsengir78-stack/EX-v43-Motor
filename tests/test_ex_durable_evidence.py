import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ex_evidence_store import restore, seal
from run_ex_production_coverage import calibration_sensitivity
from run_ex_prospective_pipeline import combine_forecasts


class DurableEvidenceTests(unittest.TestCase):
    def test_separate_records_retry_and_tamper_detection(self):
        with TemporaryDirectory() as root:
            path = Path(root)
            source, store = path / "payload", path / "store"
            source.mkdir()
            receipt = path / "receipt.json"
            receipt.write_text(json.dumps({"id": 9, "name": "ex-prospective-forecasts-2026-11-27",
                                           "created_at": "2026-11-25T08:00:00Z", "digest": "sha256:" + "0" * 64}))
            (source / "capture.json").write_text("{}")
            (source / "forecasts.jsonl").write_text("")
            seal(store, source, receipt)
            seal(store, source, receipt)
            for kind, file in (("prematch", "capture.json"), ("research-forecast", "forecasts.jsonl")):
                record = json.loads((store / "records" / kind / "9.json").read_text())
                self.assertEqual([file], list(record["files"]))
            restore(store, "prematch-and-research", path / "restored")
            self.assertEqual("{}", (path / "restored/9/capture.json").read_text())
            (source / "capture.json").write_text("different")
            with self.assertRaisesRegex(ValueError, "Existing evidence differs"):
                seal(store, source, receipt)
            for obj in (store / "objects").glob("*/*"):
                obj.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                restore(store, "prematch-and-research", path / "tamper-check")

    def test_more_matches_do_not_improve_power_under_perfect_weekly_dependence(self):
        from ex_decision import MARKETS

        rows = [{"kickoff": date, "finished": date, "labels": dict.fromkeys(MARKETS, 1),
                 "short": dict.fromkeys(MARKETS, .5), "strength": dict.fromkeys(MARKETS, s)}
                for date, s in (("2026-11-02", .49), ("2026-11-09", .55), ("2026-11-16", .61))]
        design = calibration_sensitivity(rows, (108,))["markets"]["MS1"]
        sensitivity = design["weeks_by_matches_per_week_and_assumed_intraweek_correlation"]
        self.assertLess(sensitivity["108"]["0"], sensitivity["25"]["0"])
        self.assertEqual(sensitivity["108"]["1"], sensitivity["25"]["1"])
        self.assertEqual(design["required_weeks"], sensitivity["108"]["1"])

    def test_result_sealing_rejects_post_kickoff_forecasts(self):
        from ex_history_archive import utc

        row = {"event_id": "1", "forecast_at": "2026-11-25T18:00:00Z",
               "kickoff": "2026-11-25T20:00:00Z"}
        with self.assertRaisesRegex(ValueError, "not sealed before kickoff"):
            combine_forecasts([(utc(row["kickoff"]), [row])])

    def test_weekly_domestic_baseline_uses_tracked_outcome_without_enrolling_in_venue5(self):
        from ex_daily_research import MARKET_KEYS
        from ex_historical_features import market_labels
        from run_ex_weekly_capacity import observed_coverage

        kickoff = "2026-11-25T20:00:00Z"
        teams = {"home": "11", "away": "22"}
        fixture = {"league": "UCL", "teams": teams, "kickoff": kickoff}
        daily = {"fixture": {"event_id": "1", "league": "UCL", "team_ids": teams, "kickoff_at": kickoff},
                 "as_of": "2026-11-25T07:00:00Z",
                 "domestic_research": {"baseline": dict.fromkeys(MARKET_KEYS.values(), .25)}}
        result = {"event_id": "1", **fixture, "score": [1, 0], "labels": market_labels(1, 0),
                  "settled_at": "2026-11-25T22:00:00Z",
                  "official_review": {"scope": "REVIEWED_OFFICIAL_RESULT"}}
        with TemporaryDirectory() as root:
            path = Path(root)
            pack = path / "packs" / "1"
            (pack / "forecasts").mkdir(parents=True)
            (pack / "receipt.json").write_text(json.dumps({
                "name": "ex-prospective-forecasts", "created_at": "2026-11-25T08:00:00Z"}))
            (pack / "forecasts/forecasts.jsonl").touch()
            (pack / "forecasts/daily-analysis.json").write_text(json.dumps([daily]))
            settlement = path / "settlements" / "2"
            settlement.mkdir(parents=True)
            (settlement / "receipt.json").write_text("{}")
            (settlement / "tracked-verified-outcomes.jsonl").write_text(json.dumps(result))
            counts, report = observed_coverage({"1": fixture}, path / "packs", path / "settlements")
            self.assertEqual(1, counts["UCL"]["independently_settled_domestic"])
            self.assertEqual(0, report["matched"])
            self.assertEqual(.5625, report["domestic_research"]["brier"]["MS1"])

    def test_weekly_report_uses_earliest_forecast_and_rejects_changed_outcome(self):
        from ex_decision import MARKETS
        from ex_historical_features import market_labels
        from run_ex_weekly_capacity import observed_coverage

        kickoff = "2026-11-25T20:00:00Z"
        teams = {"home": "11", "away": "22"}
        fixture = {"league": "UCL", "teams": teams, "kickoff": kickoff}
        forecast = {"event_id": "1", **fixture, "forecast_at": "2026-11-25T07:00:00Z",
                    "short": dict.fromkeys(MARKETS, .25), "strength": None}
        result = {"event_id": "1", **fixture, "score": [1, 0], "labels": market_labels(1, 0),
                  "finished": "2026-11-25T22:00:00Z", "settled_at": "2026-11-26T00:00:00Z",
                  "official_review": {"scope": "REVIEWED_OFFICIAL_RESULT"}}
        with TemporaryDirectory() as root:
            path = Path(root)
            for index, hour in ((1, 8), (2, 9)):
                folder = path / "packs" / str(index)
                folder.mkdir(parents=True)
                (folder / "receipt.json").write_text(json.dumps({
                    "name": "ex-prospective-forecasts", "created_at": f"2026-11-25T{hour:02d}:00:00Z"}))
                row = forecast if index == 1 else {**forecast, "short": dict.fromkeys(MARKETS, .99)}
                (folder / "forecasts.jsonl").write_text(json.dumps(row) + "\n")
            folder = path / "settlements" / "3"
            folder.mkdir(parents=True)
            (folder / "receipt.json").write_text("{}")
            outcomes = folder / "outcomes.jsonl"
            outcomes.write_text(json.dumps(result) + "\n")
            _, report = observed_coverage({"1": fixture}, path / "packs", path / "settlements")
            self.assertEqual(1, report["matched"])
            self.assertEqual(.5625, report["venue5_brier"]["MS1"])
            second = path / "settlements" / "4"
            second.mkdir()
            (second / "receipt.json").write_text("{}")
            (second / "outcomes.jsonl").write_text(json.dumps({
                **result, "score": [0, 1], "labels": market_labels(0, 1)}) + "\n")
            with self.assertRaisesRegex(ValueError, "Conflicting corroborated outcomes"):
                observed_coverage({"1": fixture}, path / "packs", path / "settlements")
