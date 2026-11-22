import unittest
from ex_multileague_review_batches import build
from ex_multileague_evidence_ledger import create
from ex_multileague_evidence_validation import validate

class EvidenceValidationTests(unittest.TestCase):
    def setUp(self):
        summary={"ex_final_allowed":False,"unmatched_total":1,
            "groups":[{"league":"en.1","season":"2025-26","unmatched_count":1,
                "unmatched_details":[{"date":"2025-08-01","home":"A","away":"B",
                    "source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM"}]}]}
        self.batches=build(summary)
        self.ledger=create(self.batches)

    def test_valid_pending_evidence(self):
        self.assertEqual(validate(self.ledger,self.batches)["records_checked"],1)

    def test_rejects_wrong_fixture(self):
        self.ledger["records"][0]["home"]="Wrong"
        with self.assertRaises(ValueError):
            validate(self.ledger,self.batches)

    def test_rejects_unreviewed_source_url(self):
        self.ledger["records"][0]["independent_source_url"]="https://example.org"
        with self.assertRaises(ValueError):
            validate(self.ledger,self.batches)

    def test_rejects_unreviewed_score(self):
        self.ledger["records"][0]["independent_home_goals"]=1
        with self.assertRaises(ValueError):
            validate(self.ledger,self.batches)

if __name__=="__main__":
    unittest.main()
