import datetime as dt
import unittest
from collections import Counter
from ex_live_bridge_batch import DEFAULT_CASES


class ExpandedHistoricalCasesTests(unittest.TestCase):
    def test_each_league_has_five_distinct_days(self):
        counts = Counter(league for league, _, _ in DEFAULT_CASES)
        self.assertEqual(counts, {"en.1": 5, "de.1": 5, "es.1": 5, "it.1": 5})
        self.assertEqual(len(set(DEFAULT_CASES)), 20)

    def test_no_case_after_cutoff(self):
        cutoff = dt.date(2026, 11, 22)
        for league, season, day in DEFAULT_CASES:
            with self.subTest(league=league, day=day):
                self.assertEqual(season, "2026-2027")
                self.assertLess(dt.date.fromisoformat(day), cutoff)


if __name__ == "__main__":
    unittest.main()
