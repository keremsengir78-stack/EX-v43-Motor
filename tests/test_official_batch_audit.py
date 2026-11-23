import copy
import unittest

from run_official_batch_audit import audit


class OfficialBatchAuditTests(unittest.TestCase):
    def setUp(self):
        self.queue = {"fixtures": []}
        self.batches = []
        for b in range(1, 4):
            records = []
            for j in range(25):
                idx = (b - 1) * 25 + j
                item = {"index": idx, "league": "es.1", "date": "2026-08-15",
                        "home": "Home", "away": "Away", "reference_score": [1, 0]}
                self.queue["fixtures"].append(item)
                records.append({"source_index": idx, "league": "es.1", "date": "2026-08-15",
                                "home": "Home", "away": "Away", "score": [1, 0],
                                "official_verified": False, "official_score": None,
                                "official_source_url": None})
            self.batches.append({"batch": b, "records": records, "official_verified_count": 0,
                                 "ex_final_allowed": False})

    def test_valid_queue(self):
        self.assertEqual(audit(self.queue, self.batches)["candidate_count"], 75)

    def test_duplicate_rejected(self):
        batches = copy.deepcopy(self.batches)
        batches[1]["records"][0]["source_index"] = 0
        with self.assertRaises(ValueError):
            audit(self.queue, batches)

    def test_premature_final_rejected(self):
        batches = copy.deepcopy(self.batches)
        batches[0]["ex_final_allowed"] = True
        with self.assertRaises(ValueError):
            audit(self.queue, batches)

    def test_postponed_gameweek_not_rejected_by_date(self):
        batches = copy.deepcopy(self.batches)
        record = batches[0]["records"][0]
        record["date"] = "2026-08-27"
        self.queue["fixtures"][0]["date"] = "2026-08-27"
        record["official_verified"] = True
        record["official_score"] = [1, 0]
        record["official_source_url"] = "https://www.laliga.com/en-GB/laliga-easports/results/2026-27/gameweek-1"
        batches[0]["official_verified_count"] = 1
        self.assertEqual(len(audit(self.queue, batches)["suspicious_source_scope"]), 0)


if __name__ == "__main__":
    unittest.main()
