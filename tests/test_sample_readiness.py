import unittest
from ex_sample_readiness import sample_readiness


class SampleReadinessTests(unittest.TestCase):
    def setUp(self):
        self.audit = {"technical_gate": "PASSED_AUDIT_COMPARISON",
                      "ex_final_allowed": False,
                      "cases": [
                          {"league": "en.1", "day": "2026-11-01",
                           "reviewed_matched": 5, "reviewed_unmatched": 0,
                           "reviewed_conflicts": 0},
                          {"league": "es.1", "day": "2026-11-08",
                           "reviewed_matched": 3, "reviewed_unmatched": 1,
                           "reviewed_conflicts": 0}]}

    def test_short_sample_is_never_certified(self):
        report = sample_readiness(self.audit)
        self.assertFalse(report["all_leagues_meet_diagnostic_floor"])
        self.assertFalse(report["sample_sufficiency_certified"])
        self.assertFalse(report["calibration_certified"])
        self.assertFalse(report["ex_final_allowed"])
        self.assertEqual(report["leagues"]["en.1"]["additional_days_needed"], 4)

    def test_even_large_sample_does_not_certify_model(self):
        self.audit["cases"] = [
            {"league": "en.1", "day": f"2026-11-{day:02d}",
             "reviewed_matched": 10, "reviewed_unmatched": 0,
             "reviewed_conflicts": 0} for day in range(1, 6)]
        report = sample_readiness(self.audit)
        self.assertTrue(report["all_leagues_meet_diagnostic_floor"])
        self.assertFalse(report["sample_sufficiency_certified"])
        self.assertFalse(report["ex_final_allowed"])

    def test_rejects_duplicate_day(self):
        self.audit["cases"].append(dict(self.audit["cases"][0]))
        with self.assertRaises(ValueError):
            sample_readiness(self.audit)

    def test_rejects_final_unlock(self):
        self.audit["ex_final_allowed"] = True
        with self.assertRaises(ValueError):
            sample_readiness(self.audit)

    def test_rejects_invalid_threshold(self):
        with self.assertRaises(ValueError):
            sample_readiness(self.audit, minimum_days_per_league=0)


if __name__ == "__main__":
    unittest.main()
