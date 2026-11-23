import copy
import unittest
from run_official_bulk_reconcile import reconcile


class BulkOfficialReconcileTests(unittest.TestCase):
    def setUp(self):
        self.queue = {"fixtures": []}
        self.batches = []
        for n in range(3):
            records = []
            for j in range(25):
                idx = n * 25 + j
                self.queue["fixtures"].append({"index": idx, "league": "es.1",
                    "date": "2026-08-15", "home": "Alaves", "away": "Getafe",
                    "reference_score": [3, 0]})
                records.append({"source_index": idx, "official_verified": False,
                                "official_score": None, "official_source_url": None})
            self.batches.append({"records": records, "official_verified_count": 0,
                                 "ex_final_allowed": False})

    def evidence(self, **changes):
        row = {"source_index": "0", "league": "es.1", "date": "2026-08-15",
               "home": "Alaves", "away": "Getafe", "home_goals": "3",
               "away_goals": "0", "official_source_url": "https://www.laliga.com/results",
               "source_provider": "LaLiga", "evidence_reviewed": "true"}
        row.update(changes)
        return row

    def test_bulk_match_accepted(self):
        r = reconcile(self.queue, self.batches, [self.evidence()])
        self.assertEqual(r["official_verified_total"], 0)
        self.assertEqual(r["provisional_match_indices"], [0])
        self.assertEqual(r["accepted_indices"], [])
        self.assertEqual(self.batches[0]["records"][0]["review_status"],
                         "REVIEWER_ASSERTED_SCORE_MATCH_REMOTE_CONTENT_UNVERIFIED")
        self.assertFalse(self.batches[0]["records"][0]["official_verified"])
        self.assertFalse(r["remote_content_verified_by_reconciler"])
        self.assertFalse(r["ex_final_allowed"])

    def test_non_official_host_rejected(self):
        r = reconcile(self.queue, self.batches,
                      [self.evidence(official_source_url="https://laliga.com.evil.org/results")])
        self.assertEqual(r["rejected"][0]["reason"], "NON_OFFICIAL_SOURCE_HOST")

    def test_unreviewed_evidence_rejected(self):
        r = reconcile(self.queue, self.batches, [self.evidence(evidence_reviewed="false")])
        self.assertEqual(r["official_verified_total"], 0)

    def test_score_conflict_not_approved(self):
        r = reconcile(self.queue, self.batches, [self.evidence(home_goals="2")])
        self.assertEqual(len(r["score_conflicts"]), 1)
        self.assertEqual(r["official_verified_total"], 0)

    def test_duplicate_rejected(self):
        row = self.evidence()
        r = reconcile(self.queue, self.batches, [row, copy.deepcopy(row)])
        self.assertEqual(len(r["rejected"]), 1)


if __name__ == "__main__":
    unittest.main()
