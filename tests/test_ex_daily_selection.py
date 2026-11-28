import unittest
from unittest.mock import patch

from ex_daily_selection import daily_selection
from ex_decision import MARKETS


class DailySelectionTests(unittest.TestCase):
    def test_capacity_boundary_and_small_samples(self):
        for count, name, sizes in ((29, "NORMAL", (3, 6, 3)), (30, "YOĞUN", (5, 10, 5))):
            result = daily_selection([], {str(i) for i in range(count)})
            self.assertEqual(name, result["mode"])
            self.assertEqual(sizes, tuple(result["limits"].values()))
            self.assertEqual([], result["combined"])
            self.assertEqual([], result["evidence"])

    @patch("ex_daily_selection.check_fixture", return_value={"status": "VERIFIED_INPUT"})
    def test_research_order_deduplicates_and_never_overrides_pass_or_pup(self, _):
        def match(event, p, eligible):
            values = {m: {"odds_lock": {"status": "VERIFIED_INPUT"}} for m in MARKETS}
            values["MS2"]["odds_lock"]["decision"] = "PASS_ODDS_1_19_OR_LOWER"
            return {"fixture": {"event_id": event}, "tur2": eligible, "as_of": "",
                    "venue5_research": dict.fromkeys(MARKETS, p), "market_values": values,
                    "markets": {"markets": {}}, "fixture_evidence": {"status": "FIXTURE_CROSS_VERIFIED"}}
        a, b, blocked = match("a", .6, True), match("b", .7, True), match("c", .99, False)
        result = daily_selection([a, a, b, blocked], {"a", "b", "c"}, pup_requested=True)
        self.assertEqual(["b", "a"], [x["event_id"] for x in result["combined"]])
        self.assertEqual(["b", "a"], [x["event_id"] for x in result["markets"]["KG_VAR"]])
        self.assertEqual([], result["markets"]["MS2"])
        self.assertEqual(2, len(result["evidence"]))
        self.assertEqual(3, len(result["pup"]))
        self.assertTrue(all(p["status"] == "BLOCKED" for p in result["pup"]))
        self.assertFalse(result["ex_final_allowed"])

    @patch("ex_daily_selection.check_fixture", return_value={"status": "VERIFIED_INPUT"})
    def test_batch_evidence_is_selected_only_from_combined_top_ten(self, _):
        from ex_daily_selection import combined_research_selection
        from ex_performance_v1 import CANDIDATE, KEYS

        rows = []
        for rank in range(11):
            probabilities = dict.fromkeys(KEYS.values(), .90 - rank / 100)
            prices = {market: {"odds_lock": {"status": "BLOCKED"}} for market in MARKETS}
            if rank in (4, 10):
                prices["MS1"]["odds_lock"]["status"] = "VERIFIED_INPUT"
            rows.append({"fixture": {"event_id": str(rank)}, "as_of": "", "tur2": True,
                         "domestic_research": {"baseline": probabilities},
                         "performance_v1": {CANDIDATE: probabilities}, "market_values": prices,
                         "fixture_evidence": {"status": "FIXTURE_CROSS_VERIFIED"}})

        result = combined_research_selection(rows)
        self.assertEqual([str(rank) for rank in range(10)], [row["event_id"] for row in result["combined"]])
        self.assertEqual([("4", "MS1")], [(row["event_id"], row["market"]) for row in result["evidence"]])
