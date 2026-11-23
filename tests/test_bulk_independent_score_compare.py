import unittest
from ex_bulk_independent_score_compare import compare


class BulkCompareTests(unittest.TestCase):
    def setUp(self):
        self.fixture = [{"index": 0, "date": "2025-08-16", "home": "A", "away": "B",
                         "matched_score": [1, 0], "secondary_provider": "football-data.co.uk"}]
        self.row = {"date": "2025-08-16", "home": "A", "away": "B", "home_goals": "1",
                    "away_goals": "0", "provider": "Independent Official",
                    "source_url": "https://example.org/match"}

    def test_matching_candidate_is_not_certified(self):
        result = compare(self.fixture, [self.row])
        self.assertEqual(result["counts"]["matched"], 1)
        self.assertFalse(result["independent_score_verified"])
        self.assertFalse(result["ex_final_allowed"])

    def test_mismatched_score_conflict(self):
        row = dict(self.row, away_goals="2")
        self.assertEqual(compare(self.fixture, [row])["counts"]["conflicted"], 1)

    def test_duplicate_candidate_conflict(self):
        self.assertEqual(compare(self.fixture, [self.row, self.row])["counts"]["conflicted"], 1)

    def test_same_provider_not_independent(self):
        row = dict(self.row, provider="football-data.co.uk")
        self.assertEqual(compare(self.fixture, [row])["counts"]["unresolved"], 1)

    def test_missing_candidate_unresolved(self):
        self.assertEqual(compare(self.fixture, [])["counts"]["unresolved"], 1)


    def test_invalid_https_locator_is_unresolved(self):
        for url in ("https://", "https:///match", "https://user:pass@example.org/match"):
            with self.subTest(url=url):
                self.assertEqual(compare(self.fixture, [dict(self.row, source_url=url)])["counts"]["unresolved"], 1)

    def test_invalid_fixture_date_is_unresolved(self):
        self.assertEqual(compare(self.fixture, [dict(self.row, date="2025-02-30")])["counts"]["unresolved"], 1)

    def test_score_over_thirty_is_unresolved(self):
        self.assertEqual(compare(self.fixture, [dict(self.row, home_goals="31")])["counts"]["unresolved"], 1)

    def test_non_dict_independent_row_does_not_crash(self):
        self.assertEqual(compare(self.fixture, [None, self.row])["counts"]["matched"], 1)

    def test_blank_provider_is_unresolved(self):
        self.assertEqual(compare(self.fixture, [dict(self.row, provider="  ")])["counts"]["unresolved"], 1)

    def test_invalid_score_unresolved(self):
        row = dict(self.row, home_goals="-1")
        self.assertEqual(compare(self.fixture, [row])["counts"]["unresolved"], 1)


if __name__ == "__main__":
    unittest.main()
