import unittest
from ex_match_pipeline import process_match_evidence


def record(i, season="2026", venue="home"):
    return {"fixture_id": str(i), "kickoff_at": "2026-01-%02dT12:00:00Z" % (i + 1),
            "season": season, "venue": venue, "verified": True, "source": "audited",
            "goals_for": 2, "goals_against": 1}


def inputs():
    records = [record(i) for i in range(12)] + [record(12, "2025")]
    features = {key: {"score": 0.6, "verified": True, "source": "audited",
                      "timestamp": "2026-01-20T00:00:00Z"}
                for key in ("team_strength", "match_conditions", "external_factors")}
    return records, features


class MatchPipelineTests(unittest.TestCase):
    def test_full_evidence_pipeline_is_not_final(self):
        records, features = inputs()
        result = process_match_evidence("KG_VAR", records, "home", "2026", "2025",
                                        features, "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "EVIDENCE_READY_UNCALIBRATED")
        self.assertEqual(result["evidence"]["historical"]["goals_for"]["weighted_metric"], 2)
        self.assertEqual(result["evidence"]["decision"]["weighted_score"], 0.6)
        self.assertIsNone(result["calibrated_probability"])
        self.assertFalse(result["pup_allowed"])
        self.assertFalse(result["ex_final_allowed"])

    def test_duplicate_input_blocks_before_decision(self):
        records, features = inputs()
        records.append(dict(records[0]))
        result = process_match_evidence("KG_VAR", records, "home", "2026", "2025",
                                        features, "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["evidence"])
        self.assertTrue(any("duplicate" in issue for issue in result["issues"]))

    def test_missing_previous_season_blocks(self):
        records, features = inputs()
        records = [row for row in records if row["season"] == "2026"]
        result = process_match_evidence("KG_VAR", records, "home", "2026", "2025",
                                        features, "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")

    def test_missing_feature_blocks_after_window_build(self):
        records, features = inputs()
        del features["external_factors"]
        result = process_match_evidence("KG_VAR", records, "home", "2026", "2025",
                                        features, "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("decision:external_factors:missing", result["issues"])


if __name__ == "__main__":
    unittest.main()
