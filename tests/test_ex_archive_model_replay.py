import unittest

from ex_engine import distribution
from ex_performance_v1 import score_model
from run_ex_archive_model_replay import form_samples_agree, verify_score_grid


class ArchiveModelReplayTests(unittest.TestCase):
    def test_independent_score_grid_checks_both_models(self):
        reference = distribution(1.8, .85)
        self.assertLess(verify_score_grid(reference)["max_abs_error"], 1e-12)
        candidate = score_model(1.8, .85, -.08)
        audited = verify_score_grid(candidate, -.08)
        self.assertLess(audited["max_abs_error"], 1e-12)
        self.assertAlmostEqual(candidate["score_scenarios"]["1-1"], audited["scenarios"]["1-1"])
        self.assertAlmostEqual(candidate["one_side_three_plus"], audited["scenarios"]["one_sided_three_plus"])
        self.assertGreater(verify_score_grid({**candidate, "btts": .99}, -.08)["max_abs_error"], .1)

    def test_form_rounding_tolerance_does_not_hide_window_changes(self):
        sample = {"result": [1.2, .9], "match_dates": [["2026-11-21"]]}
        original = dict.fromkeys(("home", "away"), sample)
        replayed = {**original, "home": {**sample, "result": [1.2 + 1e-15, .9]}}
        self.assertTrue(form_samples_agree(replayed, original))
        replayed["home"]["match_dates"] = [["2026-11-20"]]
        self.assertFalse(form_samples_agree(replayed, original))
