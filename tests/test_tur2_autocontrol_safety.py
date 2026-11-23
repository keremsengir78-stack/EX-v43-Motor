"""Tur-2/Auto-Control fail-closed regression for independent source evidence."""
import unittest

from ex_auto_control import auto_control, snapshot


def match():
    return {
        "status": "BASELINE_ONLY",
        "recompute_consistent": True,
        "fixture_lock": {"status": "VERIFIED_INPUT"},
        "odds_lock": {"status": "VERIFIED_INPUT"},
        "market_baselines_pct": {
            "MS1": 45, "MSX": 30, "MS2": 25,
            "KG_VAR": 55, "2.5_UST": 52,
        },
    }


def ingestion():
    return {"status": "INGESTED_CROSS_VERIFIED",
            "independent_sources_confirmed": 2}


class Tur2AutoControlSafetyTests(unittest.TestCase):
    def assert_locked(self, result):
        self.assertEqual(result["status"], "BLOCKED")
        self.assertFalse(result["ex_final_allowed"])

    def test_consistent_snapshot_is_deterministic_but_not_independent_evidence(self):
        item = match()
        self.assertEqual(snapshot(item), snapshot(dict(reversed(list(item.items())))))
        result = auto_control(item, ingestion())
        self.assert_locked(result)
        self.assertIn("exg:uncalibrated", result["issues"])
        self.assertIn("pup:unverified", result["issues"])

    def test_one_source_never_satisfies_independent_source_gate(self):
        item = ingestion()
        item["independent_sources_confirmed"] = 1
        result = auto_control(match(), item)
        self.assert_locked(result)
        self.assertIn("second_source:unverified", result["issues"])

    def test_boolean_source_count_is_rejected(self):
        item = ingestion()
        item["independent_sources_confirmed"] = True
        result = auto_control(match(), item)
        self.assert_locked(result)
        self.assertIn("second_source:unverified", result["issues"])

    def test_tur2_mismatch_is_explicitly_blocked(self):
        item = match()
        item["recompute_consistent"] = False
        result = auto_control(item, ingestion())
        self.assert_locked(result)
        self.assertIn("tur2:recompute_mismatch", result["issues"])

    def test_market_result_probability_sum_is_checked(self):
        item = match()
        item["market_baselines_pct"]["MS2"] = 30
        result = auto_control(item, ingestion())
        self.assert_locked(result)
        self.assertIn("match_result_probabilities:sum_mismatch", result["issues"])


if __name__ == "__main__":
    unittest.main()
