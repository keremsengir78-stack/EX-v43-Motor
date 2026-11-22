import unittest

from ex_evidence_pipeline import prepare_market_evidence


def fixture(i):
    return {"fixture_id": str(i), "kickoff_at": "2026-01-%02dT10:00:00Z" % (i + 1),
            "source": "audited", "verified": True, "goals_for": 2, "goals_against": 1}


def valid_inputs():
    ten = [fixture(i) for i in range(9, -1, -1)]
    windows = {"venue_last5": ten[:5], "venue_last10": ten,
               "current_season": [fixture(15)], "previous_venue": [fixture(14)]}
    features = {key: {"score": 0.5, "verified": True, "source": "audited",
                      "timestamp": "2026-01-20T00:00:00Z"}
                for key in ("team_strength", "match_conditions", "external_factors")}
    return windows, features


class EvidencePipelineTests(unittest.TestCase):
    def test_verified_inputs_still_not_final(self):
        windows, features = valid_inputs()
        result = prepare_market_evidence("KG_VAR", windows, features, "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "EVIDENCE_READY_UNCALIBRATED")
        self.assertEqual(result["historical"]["goals_for"]["weighted_metric"], 2)
        self.assertEqual(result["historical"]["goals_against"]["weighted_metric"], 1)
        self.assertEqual(result["decision"]["weighted_score"], 0.5)
        self.assertIsNone(result["calibrated_probability"])
        self.assertFalse(result["pup_allowed"])
        self.assertFalse(result["ex_final_allowed"])

    def test_missing_historical_data_blocks(self):
        windows, features = valid_inputs()
        del windows["venue_last5"]
        result = prepare_market_evidence("KG_VAR", windows, features, "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertTrue(any("historical:goals_for" in x for x in result["issues"]))

    def test_missing_decision_feature_blocks(self):
        windows, features = valid_inputs()
        del features["external_factors"]
        result = prepare_market_evidence("KG_VAR", windows, features, "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("decision:external_factors:missing", result["issues"])

    def test_unsupported_market_blocks(self):
        windows, features = valid_inputs()
        result = prepare_market_evidence("MSX", windows, features, "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("market:unsupported", result["issues"])


if __name__ == "__main__":
    unittest.main()
