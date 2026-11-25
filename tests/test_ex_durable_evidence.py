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
            receipt.write_text(json.dumps({"id": 9, "name": "ex-prospective-forecasts",
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
