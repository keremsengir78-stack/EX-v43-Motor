"""Canonical UTC timestamp safety checks for EX historical calibration."""
import unittest

from ex_calibration_audit import audit_predictions


def records():
    return [
        {"fixture_id": "fixture-%03d" % i, "market": "KG_VAR",
         "probability": 0.6, "outcome": i % 2,
         "predicted_at": "2026-10-01T09:00:00Z",
         "kickoff_at": "2026-10-01T12:00:00Z",
         "settled_at": "2026-10-01T14:00:00Z"}
        for i in range(30)
    ]


class CanonicalCalibrationTimestampTests(unittest.TestCase):
    def audit(self, entries, cutoff="2026-10-02T00:00:00Z"):
        return audit_predictions(entries, "KG_VAR", cutoff, min_samples=30)

    def test_canonical_historical_sample_is_audit_only(self):
        result = self.audit(records())
        self.assertEqual(result["status"], "AUDIT_COMPLETE_NOT_CALIBRATED")
        self.assertFalse(result["calibration_certified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_iso_week_cutoff_is_rejected(self):
        result = self.audit(records(), "2026-W40-5T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("cutoff:invalid", result["issues"])

    def test_compact_cutoff_is_rejected(self):
        result = self.audit(records(), "20261002T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("cutoff:invalid", result["issues"])

    def test_noncanonical_prediction_time_is_rejected(self):
        for value in ("20261001T09:00:00Z", "2026-W40-4T09:00:00Z",
                      "2026-10-01T09:00Z", "2026-10-01T09:00:00+00:00"):
            with self.subTest(value=value):
                entries = records()
                entries[0]["predicted_at"] = value
                result = self.audit(entries)
                self.assertEqual(result["status"], "BLOCKED")
                self.assertIn("record:0:invalid_timestamp", result["issues"])

    def test_noncanonical_settlement_time_is_rejected(self):
        entries = records()
        entries[0]["settled_at"] = "2026-10-01T14:00Z"
        result = self.audit(entries)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("record:0:invalid_timestamp", result["issues"])


if __name__ == "__main__":
    unittest.main()
