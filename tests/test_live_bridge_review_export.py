import unittest
from ex_live_bridge_review_export import review_rows


def report():
    return {"ex_final_allowed": False, "as_of": "2026-11-22", "reviewed_unmatched": 1,
            "review_queue": [{"league": "es.1", "day": "2026-11-08",
                "unmatched": 1, "fixtures": [{
                    "league": "es.1", "date": "2026-11-08",
                    "home": "Elche", "away": "Real Betis", "reason": "not_found"}]}]}


class ReviewExportTests(unittest.TestCase):
    def test_export_keeps_review_required(self):
        rows = review_rows(report())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["review_status"], "REQUIRES_INDEPENDENT_SOURCE_REVIEW")
        self.assertEqual(rows[0]["as_of"], "2026-11-22")
        self.assertEqual(rows[0]["source_reference"], "NOT_VERIFIED")

    def test_export_is_sorted_deterministically(self):
        data = report()
        data["review_queue"][0]["fixtures"].insert(0, {
            "league": "es.1", "date": "2026-11-08",
            "home": "Real Sociedad", "away": "Rayo Vallecano", "reason": "not_found"})
        data["review_queue"][0]["unmatched"] = 2
        data["reviewed_unmatched"] = 2
        self.assertEqual([row["home"] for row in review_rows(data)], ["Elche", "Real Sociedad"])

    def test_regressed_baseline_rejected(self):
        data = report()
        data["technical_gate"] = "FAILED_REGRESSION"
        with self.assertRaises(ValueError):
            review_rows(data)

    def test_inconsistent_reason_count_rejected(self):
        data = report()
        data["review_queue"][0]["reason_counts"] = {"not_found": 2}
        with self.assertRaises(ValueError):
            review_rows(data)

    def test_future_fixture_rejected(self):
        data = report()
        data["review_queue"][0]["day"] = "2026-11-23"
        data["review_queue"][0]["fixtures"][0]["date"] = "2026-11-23"
        with self.assertRaises(ValueError):
            review_rows(data)

    def test_invalid_cutoff_rejected(self):
        data = report()
        data["as_of"] = "tomorrow"
        with self.assertRaises(ValueError):
            review_rows(data)

    def test_final_gate_must_be_blocked(self):
        data = report()
        data["ex_final_allowed"] = True
        with self.assertRaises(ValueError):
            review_rows(data)

    def test_missing_fixture_rejected(self):
        data = report()
        data["review_queue"][0]["fixtures"] = []
        with self.assertRaises(ValueError):
            review_rows(data)

    def test_wrong_league_rejected(self):
        data = report()
        data["review_queue"][0]["fixtures"][0]["league"] = "de.1"
        with self.assertRaises(ValueError):
            review_rows(data)

    def test_duplicate_fixture_rejected(self):
        data = report()
        data["review_queue"][0]["fixtures"] *= 2
        data["review_queue"][0]["unmatched"] = 2
        data["reviewed_unmatched"] = 2
        with self.assertRaises(ValueError):
            review_rows(data)


if __name__ == "__main__":
    unittest.main()
