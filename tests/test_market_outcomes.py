import unittest
from ex_market_outcomes import market_outcomes


def match(fid, home, away, **updates):
    row = {"fixture_id": fid, "kickoff_at": "2026-01-01T12:00:00Z",
           "home_goals": home, "away_goals": away, "verified": True,
           "source": "audited", "status": "finished"}
    row.update(updates)
    return row


class MarketOutcomeTests(unittest.TestCase):
    def test_non_utc_cutoff_is_blocked(self):
        result = market_outcomes([match("a", 2, 1)],
                                 "2026-02-01T03:00:00+03:00Z")
        self.assertIn("as_of:invalid", result["issues"])

    def test_non_utc_kickoff_is_blocked(self):
        result = market_outcomes(
            [match("a", 2, 1, kickoff_at="2026-01-01T15:00:00+03:00Z")],
            "2026-02-01T00:00:00Z")
        self.assertIn("fixture:0:date_invalid_or_future", result["issues"])

    def test_matching_non_utc_cutoff_and_kickoff_block(self):
        result = market_outcomes(
            [match("a", 2, 1, kickoff_at="2026-01-01T15:00:00+03:00Z")],
            "2026-02-01T03:00:00+03:00Z")
        self.assertEqual(result["status"], "BLOCKED")

    def test_utc_labels_remain_unfinalized(self):
        result = market_outcomes([match("a", 2, 1)], "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "OUTCOMES_READY")
        self.assertFalse(result["ex_final_allowed"])

    def test_four_markets_are_independent(self):
        result = market_outcomes([match("a", 2, 1), match("b", 0, 3),
                                  match("c", 1, 1), match("d", 0, 0)],
                                 "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "OUTCOMES_READY")
        labels = result["outcomes"]
        self.assertEqual([(x["MS1"], x["MS2"], x["KG_VAR"], x["2.5_UST"]) for x in labels],
                         [(1, 0, 1, 1), (0, 1, 0, 1), (0, 0, 1, 0), (0, 0, 0, 0)])
        self.assertFalse(result["ex_final_allowed"])

    def test_duplicate_blocks_every_label(self):
        result = market_outcomes([match("a", 1, 0), match("a", 1, 0)],
                                 "2026-02-01T00:00:00Z")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["outcomes"], [])

    def test_unfinished_blocks(self):
        result = market_outcomes([match("a", 1, 0, status="live")],
                                 "2026-02-01T00:00:00Z")
        self.assertIn("fixture:0:not_finished", result["issues"])

    def test_boolean_score_blocks(self):
        result = market_outcomes([match("a", True, 0)], "2026-02-01T00:00:00Z")
        self.assertIn("fixture:0:score_invalid", result["issues"])

    def test_future_match_blocks(self):
        result = market_outcomes([match("a", 1, 0)], "2025-12-31T00:00:00Z")
        self.assertIn("fixture:0:date_invalid_or_future", result["issues"])

    def test_unverified_match_blocks(self):
        result = market_outcomes([match("a", 1, 0, verified=False)],
                                 "2026-02-01T00:00:00Z")
        self.assertIn("fixture:0:unverified", result["issues"])


if __name__ == "__main__":
    unittest.main()
