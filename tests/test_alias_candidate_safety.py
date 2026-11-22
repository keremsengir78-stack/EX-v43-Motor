import unittest

from ex_cross_verify import unresolved_pairs


def match(home, away, hg=1, ag=0):
    return {"date": "2026-11-08", "league": "it.1",
            "home": home, "away": away, "home_goals": hg, "away_goals": ag}


class AliasCandidateSafetyTests(unittest.TestCase):
    def test_same_score_without_opponent_is_not_alias_evidence(self):
        primary = [match("Genoa", "AC Milan")]
        secondary = [match("Roma", "Lazio")]
        self.assertEqual(unresolved_pairs(primary, secondary, "2026-11-22"), [])

    def test_matching_opponent_can_suggest_manual_review(self):
        suggestions = unresolved_pairs(
            [match("Genoa", "AC Milan")], [match("Genoa", "Milan")], "2026-11-22")
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["status"], "REVIEW_REQUIRED")
        self.assertEqual(suggestions[0]["basis"], "unique_date_and_opponent_candidate")

    def test_multiple_same_opponent_candidates_are_not_suggested(self):
        primary = [match("Genoa", "AC Milan")]
        secondary = [match("Genoa", "Milan"), match("Genoa", "Inter")]
        self.assertEqual(unresolved_pairs(primary, secondary, "2026-11-22"), [])

    def test_cutoff_excludes_future_alias_suggestions(self):
        self.assertEqual(unresolved_pairs(
            [match("Genoa", "AC Milan")], [match("Genoa", "Milan")], "2026-11-08"), [])


if __name__ == "__main__":
    unittest.main()
