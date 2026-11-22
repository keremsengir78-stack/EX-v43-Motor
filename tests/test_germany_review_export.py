import json
import unittest
from ex_germany_review_export import germany_rows


class GermanyReviewExportTests(unittest.TestCase):
    def test_only_germany_and_preserves_identity(self):
        audit = {"ex_final_allowed": False, "secondary_unverified": 2,
                 "secondary_unmatched_by_season": {"2026-27/de.1": 1, "2026-27/es.1": 1},
                 "secondary_review_queue": [
                     {"season": "2026-27", "league": "de.1",
                      "unmatched": [{"date": "2026-11-08", "home": "A", "away": "B",
                                     "source_diagnostic": {"candidate": "Bayern"}}]},
                     {"season": "2026-27", "league": "es.1",
                      "unmatched": [{"date": "2026-11-08", "home": "C", "away": "D"}]}]}
        rows = germany_rows(audit)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["league"], rows[0]["home"]), ("de.1", "A"))
        self.assertEqual(rows[0]["review_status"], "REQUIRES_INDEPENDENT_SOURCE_REVIEW")
        self.assertEqual(json.loads(rows[0]["source_evidence_json"])["source_diagnostic"],
                         {"candidate": "Bayern"})

    def test_invalid_evidence_fails_closed(self):
        audit = {"ex_final_allowed": False, "secondary_unverified": 1,
                 "secondary_review_queue": [
                     {"season": "2026-27", "league": "de.1", "unmatched": [None]}]}
        with self.assertRaises(ValueError):
            germany_rows(audit)
