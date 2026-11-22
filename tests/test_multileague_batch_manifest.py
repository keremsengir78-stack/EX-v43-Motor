import unittest
from ex_multileague_review_batches import build
from ex_multileague_batch_manifest import manifest

class BatchManifestTests(unittest.TestCase):
    def setUp(self):
        self.source={"ex_final_allowed":False,"unmatched_total":1,
            "groups":[{"league":"en.1","season":"2025-26","unmatched_count":1,
                "unmatched_details":[{"date":"2025-08-01","home":"A","away":"B",
                    "source_presence_status":"SECONDARY_SAME_DAY_SHARED_TEAM"}]}]}

    def test_hash_is_stable(self):
        batches=build(self.source)
        self.assertEqual(manifest(batches),manifest(batches))
        self.assertEqual(len(manifest(batches)["batches"][0]["sha256"]),64)

    def test_hash_changes_with_fixture(self):
        batches=build(self.source)
        old=manifest(batches)["batches"][0]["sha256"]
        batches["batches"][0]["fixtures"][0]["home"]="Different"
        self.assertNotEqual(old,manifest(batches)["batches"][0]["sha256"])

    def test_rejects_approved_score(self):
        batches=build(self.source)
        batches["batches"][0]["fixtures"][0]["independent_score_verified"]=True
        with self.assertRaises(ValueError):
            manifest(batches)

if __name__=="__main__":
    unittest.main()
