import copy
import unittest

from run_external_candidate_integrity_audit import audit


class ExternalCandidateAuditTests(unittest.TestCase):
    def setUp(self):
        self.original = {"verified": [{"fixture": {"league": "en.1", "season": "2026-27",
            "date": "2026-08-21", "home": "Arsenal FC", "away": "Coventry City FC"},
            "score": [3, 0]} for _ in range(75)]}
        for i in range(37, 68):
            self.original["verified"][i]["fixture"]["league"] = "es.1"
        for i in range(68, 75):
            self.original["verified"][i]["fixture"]["league"] = "it.1"
        self.queue = {"candidate_count": 75, "independent_score_verified": False,
                      "ex_final_allowed": False, "by_league": {"en.1": 37, "es.1": 31, "it.1": 7},
                      "fixtures": []}
        for i, item in enumerate(self.original["verified"]):
            f = item["fixture"]
            self.queue["fixtures"].append({"index": i, "league": f["league"], "date": f["date"],
                "home": f["home"], "away": f["away"], "reference_score": [3, 0],
                "other_score": [3, 0], "provider": "fixturedl",
                "status": "SCORE_MATCH_CANDIDATE",
                "source_url": "https://github.com/oladeeayo/open-matchday/blob/master/data/test.csv"})

    def test_valid_queue(self):
        self.assertEqual(audit(self.original, self.queue)["independent_verified_by_this_audit"], 0)

    def test_duplicate_index(self):
        bad = copy.deepcopy(self.queue)
        bad["fixtures"][1]["index"] = 0
        with self.assertRaises(ValueError):
            audit(self.original, bad)

    def test_tampered_score(self):
        bad = copy.deepcopy(self.queue)
        bad["fixtures"][0]["other_score"] = [0, 3]
        with self.assertRaises(ValueError):
            audit(self.original, bad)

    def test_premature_final(self):
        bad = copy.deepcopy(self.queue)
        bad["ex_final_allowed"] = True
        with self.assertRaises(ValueError):
            audit(self.original, bad)

    def test_bad_provenance(self):
        bad = copy.deepcopy(self.queue)
        bad["fixtures"][0]["source_url"] = "https://other.example/match"
        with self.assertRaises(ValueError):
            audit(self.original, bad)


if __name__ == "__main__":
    unittest.main()
