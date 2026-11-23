import unittest
from ex_source_time_gate import audit_source_times

BASE = dict(kickoff_at="2026-11-23T12:00:00Z",
            published_at="2026-11-23T14:00:00Z",
            captured_at="2026-11-23T14:05:00Z",
            checked_at="2026-11-23T14:10:00Z")


class SourceTimeGateTests(unittest.TestCase):
    def check_issue(self, issue, **changes):
        data = dict(BASE, **changes)
        result = audit_source_times(**data)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(issue, result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_consistent_is_still_unattested(self):
        result = audit_source_times(**BASE)
        self.assertEqual(result["status"], "TIME_CONSISTENT_UNATTESTED")
        self.assertFalse(result["live_fetch_attested"])
        self.assertFalse(result["official_source_attested"])
        self.assertFalse(result["ex_final_allowed"])

    def test_publication_before_kickoff(self):
        self.check_issue("published_before_kickoff", published_at="2026-11-23T11:59:59Z")

    def test_capture_before_publication(self):
        self.check_issue("captured_before_publication", captured_at="2026-11-23T13:59:59Z")

    def test_checked_before_capture(self):
        self.check_issue("checked_before_capture", checked_at="2026-11-23T14:04:59Z")

    def test_stale_capture(self):
        self.check_issue("stale_capture", checked_at="2026-11-25T14:10:00Z")

    def test_invalid_and_noncanonical_dates(self):
        for timestamp in ("2026-02-30T12:00:00Z", "2026-11-23T12:00:00+00:00",
                          "2026-11-23T12:00Z", None):
            self.check_issue("invalid_timestamp", captured_at=timestamp)

    def test_invalid_age_configuration(self):
        for age in (-1, True, 1.5):
            self.check_issue("invalid_maximum_age", maximum_capture_age_seconds=age)


if __name__ == "__main__":
    unittest.main()
