import unittest
from ex_germany_strict_batch import build


class GermanStrictBatchTests(unittest.TestCase):
    def setUp(self):
        self.row={"season":"2026-27","league":"de.1","date":"2026-08-29",
                  "home":"1. FSV Mainz 05","away":"SC Paderborn 07","reason":"not_found"}
        self.data={"ex_final_allowed":False,"aliases_approved":False,"fixtures":[self.row]}

    def test_quarantined_fixture_preserves_identity(self):
        result=build(self.data)
        self.assertFalse(result["ex_final_allowed"])
        self.assertEqual(result["batches"][0]["fixtures"][0]["away"],"SC Paderborn 07")
        self.assertNotIn("reason",result["batches"][0]["fixtures"][0])

    def test_final_unlock_rejected(self):
        self.data["ex_final_allowed"]=True
        with self.assertRaises(ValueError):
            build(self.data)

    def test_approved_aliases_rejected(self):
        self.data["aliases_approved"]=True
        with self.assertRaises(ValueError):
            build(self.data)

    def test_duplicate_fixture_rejected(self):
        self.data["fixtures"].append(dict(self.row))
        with self.assertRaises(ValueError):
            build(self.data)

    def test_wrong_league_rejected(self):
        self.row["league"]="en.1"
        with self.assertRaises(ValueError):
            build(self.data)


if __name__=="__main__":
    unittest.main()
