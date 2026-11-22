import unittest
from ex_multileague_review_batches import build
from ex_multileague_evidence_ledger import create

class EvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        summary={"ex_final_allowed":False,"unmatched_total":1,
            "groups":[{"league":"en.1","season":"2025-26","unmatched_count":1,
                "unmatched_details":[{"date":"2025-08-01","home":"A","away":"B",
                    "source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM"}]}]}
        self.batches=build(summary)

    def test_pending_evidence_is_not_verified(self):
        ledger=create(self.batches)
        self.assertEqual(ledger["total_records"],1)
        self.assertIsNone(ledger["records"][0]["independent_source_url"])
        self.assertFalse(ledger["records"][0]["score_confirmed"])
        self.assertFalse(ledger["ex_final_allowed"])

    def test_rejects_missing_batch(self):
        with self.assertRaises(ValueError):
            create(self.batches,2)

    def test_rejects_premature_approval(self):
        self.batches["batches"][0]["fixtures"][0]["independent_score_verified"]=True
        with self.assertRaises(ValueError):
            create(self.batches)

if __name__=="__main__":
    unittest.main()
