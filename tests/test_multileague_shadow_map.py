import unittest
from ex_multileague_shadow_map import build


def report(rows):
    return {"ex_final_allowed":False,"score_verified":False,"aliases_approved":False,
            "candidates":rows}


def row(p,s,league="fr.1"):
    return {"league":league,"primary_name":p,"secondary_name":s,
            "mapping_conflict":False,"auto_approved":False,
            "review_status":"MANUAL_REVIEW_REQUIRED"}


class MultiLeagueShadowMapTests(unittest.TestCase):
    def test_reverse_provider_alias_only(self):
        self.assertEqual(build(report([row("Olympique Lyonnais","Lyon")])),
                         {"fr.1":{"Lyon":"Olympique Lyonnais"}})

    def test_rejects_one_to_many(self):
        with self.assertRaises(ValueError):
            build(report([row("A","X"),row("B","X")]))

    def test_rejects_approved(self):
        with self.assertRaises(ValueError):
            build(report([{**row("A","X"),"auto_approved":True}]))


if __name__=="__main__":
    unittest.main()
