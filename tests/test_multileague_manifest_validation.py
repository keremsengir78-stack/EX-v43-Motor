import unittest
from ex_multileague_review_batches import build
from ex_multileague_batch_manifest import manifest
from ex_multileague_manifest_validation import validate

class ManifestValidationTests(unittest.TestCase):
    def setUp(self):
        summary={"ex_final_allowed":False,"unmatched_total":1,
            "groups":[{"league":"en.1","season":"2025-26","unmatched_count":1,
                "unmatched_details":[{"date":"2025-08-01","home":"A","away":"B",
                    "source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM"}]}]}
        self.batches=build(summary)

    def test_recomputes_hashes(self):
        self.assertEqual(validate(self.batches,manifest(self.batches))["hashes_verified"],1)

    def test_rejects_tampered_digest(self):
        altered=manifest(self.batches)
        altered["batches"][0]["sha256"]="0"*64
        with self.assertRaises(ValueError):
            validate(self.batches,altered)

    def test_rejects_missing_batch(self):
        altered=manifest(self.batches)
        altered["batches"]=[]
        with self.assertRaises(ValueError):
            validate(self.batches,altered)

if __name__=="__main__":
    unittest.main()
