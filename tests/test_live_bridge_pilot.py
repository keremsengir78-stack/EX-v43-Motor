import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ex_live_bridge_pilot as pilot


class LiveBridgePilotTests(unittest.TestCase):
    def test_provisional_match_never_certifies_final(self):
        with patch.object(pilot, "fetch_and_compare_historical_day", return_value={
            "status": "PROVISIONAL_MATCH_UNAUDITED", "issues": [],
            "comparison": {"matched": 3, "unmatched": 0, "ambiguous": 0, "conflicts": []},
            "provenance": {"espn": {"sha256": "abc"}}}):
            result = pilot.run_pilot("en.1", "2026-2027", "2026-11-01", "2026-11-22")
        self.assertEqual(result["matched"], 3)
        self.assertEqual(result["coverage"], 0)
        self.assertEqual(result["conflict_count"], 0)
        self.assertFalse(result["ex_final_allowed"])
        self.assertFalse(result["calibration_certified"])

    def test_conflict_is_preserved(self):
        conflict = {"home": "Arsenal", "away": "Chelsea"}
        with patch.object(pilot, "fetch_and_compare_historical_day", return_value={
            "status": "SCORE_CONFLICT", "issues": [],
            "comparison": {"matched": 1, "unmatched": 0, "ambiguous": 0, "conflicts": [conflict]}}):
            result = pilot.run_pilot("en.1", "2026-2027", "2026-11-01", "2026-11-22")
        self.assertEqual(result["conflicts"], [conflict])
        self.assertEqual(result["conflict_count"], 1)
        self.assertFalse(result["ex_final_allowed"])

    def test_blocked_fetch_stays_blocked(self):
        with patch.object(pilot, "fetch_and_compare_historical_day", return_value={
            "status": "BLOCKED", "issues": ["espn:fetch_or_parse_failed"],
            "comparison": None}):
            result = pilot.run_pilot("en.1", "2026-2027", "2026-11-01", "2026-11-22")
        self.assertEqual(result["matched"], 0)
        self.assertIn("espn:fetch_or_parse_failed", result["issues"])

    def test_report_json_serializable(self):
        with patch.object(pilot, "fetch_and_compare_historical_day", return_value={
            "status": "BLOCKED", "issues": [], "comparison": None}):
            result = pilot.run_pilot("en.1", "2026-2027", "2026-11-01", "2026-11-22")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.json"
            path.write_text(json.dumps(result))
            self.assertFalse(json.loads(path.read_text())["ex_final_allowed"])

    def test_unexpected_fetch_exception_is_audited(self):
        with patch.object(pilot, "fetch_and_compare_historical_day", side_effect=RuntimeError("secret")):
            result = pilot.run_pilot("en.1", "2026-2027", "2026-11-01", "2026-11-22")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("pilot:unexpected_error:RuntimeError", result["issues"])
        self.assertNotIn("secret", json.dumps(result))
        self.assertFalse(result["ex_final_allowed"])

    def test_comparison_metrics_preserved(self):
        with patch.object(pilot, "fetch_and_compare_historical_day", return_value={
            "status": "PARTIAL_PROVISIONAL_MATCH", "issues": [],
            "comparison": {"matched": 2, "unmatched": 1, "ambiguous": 1,
                           "conflicts": [], "coverage": 0.6667,
                           "alias_suggestion_count": 3, "status": "PARTIAL_VERIFICATION"}}):
            result = pilot.run_pilot("en.1", "2026-2027", "2026-11-01", "2026-11-22")
        self.assertEqual(result["coverage"], 0.6667)
        self.assertEqual(result["alias_suggestion_count"], 3)
        self.assertEqual(result["source_agreement_status"], "PARTIAL_VERIFICATION")
        self.assertFalse(result["ex_final_allowed"])

    def test_provenance_is_retained(self):
        provenance = {"espn": {"sha256": "123"}, "football_data": {"url": "https://example.test"}}
        with patch.object(pilot, "fetch_and_compare_historical_day", return_value={
            "status": "PARTIAL_PROVISIONAL_MATCH", "issues": [],
            "comparison": {"matched": 1, "unmatched": 2, "ambiguous": 0, "conflicts": []},
            "provenance": provenance}):
            result = pilot.run_pilot("en.1", "2026-2027", "2026-11-01", "2026-11-22")
        self.assertEqual(result["provenance"], provenance)
        self.assertEqual(result["unmatched"], 2)


if __name__ == "__main__":
    unittest.main()
