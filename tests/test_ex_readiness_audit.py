import unittest
from run_ex_readiness_audit import build_report


class ReadinessAuditTests(unittest.TestCase):
    def setUp(self):
        self.queue = {"fixtures": []}
        self.batches = []
        for n in range(3):
            rows = []
            for j in range(25):
                i = n * 25 + j
                self.queue["fixtures"].append({"index": i, "league": "es.1",
                    "date": "2026-08-15", "home": "A", "away": "B", "reference_score": [1, 0]})
                rows.append({"source_index": i, "league": "es.1",
                    "date": "2026-08-15", "home": "A", "away": "B",
                    "score": [1, 0], "official_verified": False})
            self.batches.append({"records": rows})
        self.broadcaster = {"records": []}

    def test_unverified_remains_open(self):
        result = build_report(self.queue, self.batches, self.broadcaster)
        self.assertEqual(result["open_review_count"], 75)
        self.assertFalse(result["ex_final_allowed"])

    def test_generic_official_page_not_certified(self):
        row = self.batches[0]["records"][0]
        row.update(official_verified=True, official_score=[1, 0],
                   official_source_url="https://www.laliga.com/results/2026-27/gameweek-1")
        result = build_report(self.queue, self.batches, self.broadcaster)
        self.assertEqual(result["classification"]["official_page_level_claims_pending_exact_fixture_proof"], 1)
        self.assertEqual(result["automatically_certified_exact_match_results"], 0)

    def test_wrong_score_rejected(self):
        row = self.batches[0]["records"][0]
        row.update(official_verified=True, official_score=[2, 0],
                   official_source_url="https://www.laliga.com/results/2026-27/gameweek-1")
        with self.assertRaises(ValueError):
            build_report(self.queue, self.batches, self.broadcaster)

    def test_unsupported_broadcaster_match_rejected(self):
        self.broadcaster["records"] = [{
            "source_index": 0, "independent_broadcaster_match": True,
            "independent_broadcaster_score": [1, 0],
        }]
        self.broadcaster["matching_score_count"] = 1
        with self.assertRaises(ValueError):
            build_report(self.queue, self.batches, self.broadcaster)

    def test_pending_broadcaster_is_not_verified(self):
        self.broadcaster["records"] = [{
            "source_index": 0, "independent_broadcaster_match": False,
            "independent_broadcaster_score": None,
        }]
        result = build_report(self.queue, self.batches, self.broadcaster)
        self.assertEqual(result["classification"]["broadcaster_evidence_not_extracted"], 1)

    def test_pending_broadcaster_with_copied_score_rejected(self):
        self.broadcaster["records"] = [{
            "source_index": 0, "independent_broadcaster_match": False,
            "independent_broadcaster_score": [1, 0],
        }]
        with self.assertRaises(ValueError):
            build_report(self.queue, self.batches, self.broadcaster)

    def test_inconsistent_broadcaster_count_rejected(self):
        self.broadcaster["matching_score_count"] = 37
        with self.assertRaises(ValueError):
            build_report(self.queue, self.batches, self.broadcaster)

    def test_duplicate_rejected(self):
        self.batches[1]["records"][0]["source_index"] = 0
        with self.assertRaises(ValueError):
            build_report(self.queue, self.batches, self.broadcaster)


if __name__ == "__main__":
    unittest.main()
