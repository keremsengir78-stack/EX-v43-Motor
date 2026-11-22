import unittest
from ex_live_bridge_review_export import review_rows


def report():
    return {"ex_final_allowed": False, "as_of": "2026-11-22", "reviewed_unmatched": 1,
            "technical_gate": "PASSED_AUDIT_COMPARISON",
            "review_queue_complete": True, "review_queue_missing_count": 0,
            "data_gate": "BLOCKED_UNRESOLVED_FIXTURES",
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

    def test_export_preserves_venue_diagnostics(self):
        data = report()
        fixture = data["review_queue"][0]["fixtures"][0]
        fixture.update({"secondary_home_team_count": 1,
                        "secondary_away_team_count": 0,
                        "secondary_reversed_fixture_count": 0})
        row = review_rows(data)[0]
        self.assertEqual(row["secondary_home_team_count"], 1)
        self.assertEqual(row["secondary_away_team_count"], 0)
        self.assertEqual(row["secondary_reversed_fixture_count"], 0)
        self.assertEqual(row["source_reference"], "NOT_VERIFIED")

    def test_export_is_sorted_deterministically(self):
        data = report()
        data["review_queue"][0]["fixtures"].insert(0, {
            "league": "es.1", "date": "2026-11-08",
            "home": "Real Sociedad", "away": "Rayo Vallecano", "reason": "not_found"})
        data["review_queue"][0]["unmatched"] = 2
        data["reviewed_unmatched"] = 2
        self.assertEqual([row["home"] for row in review_rows(data)], ["Elche", "Real Sociedad"])

    def test_truncated_review_evidence_rejected(self):
        data = report()
        data["review_queue_complete"] = False
        data["review_queue_missing_count"] = 1
        with self.assertRaises(ValueError):
            review_rows(data)

    def test_missing_technical_gate_rejected(self):
        data = report()
        del data["technical_gate"]
        with self.assertRaises(ValueError):
            review_rows(data)

    def test_contradictory_data_gate_rejected(self):
        data = report()
        data["data_gate"] = "PROVISIONAL_COVERAGE_ONLY"
        with self.assertRaises(ValueError):
            review_rows(data)

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

    def test_same_fixture_with_different_reason_rejected(self):
        data = report()
        duplicate = dict(data["review_queue"][0]["fixtures"][0])
        duplicate["reason"] = "ambiguous"
        data["review_queue"][0]["fixtures"].append(duplicate)
        data["review_queue"][0]["unmatched"] = 2
        data["reviewed_unmatched"] = 2
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
