from datetime import date
import unittest

from run_ex_dutch_reconcile import parse_knvb, parse_vi, reconcile
from run_ex_source_audit import audit


class ProductionCoverageTests(unittest.TestCase):
    def test_dutch_identity_keeps_home_away_date_and_considers_both_publishers(self):
        html = ('<span class="title"><span>23 november 2026</span></span>'
                '<div class="row"><div class="value home"><div class="team">Jong Ajax</div></div>'
                '<div class="value center">3-0</div><div class="value away"><div class="team">Jong AZ</div></div></div>')
        results = parse_knvb(html, date(2026, 11, 25))
        vi = ('<a class="MatchList_match-link__a" href="/wedstrijden/2026-11-23/jong-ajax-vs-jong-az">'
              '<span>FT</span><ul class="score-element ScoreElement_a"><li>3</li><li>1</li></ul></a>')
        other = parse_vi(vi, date(2026, 11, 25))
        primary = {"date": "2026-11-23", "home": "Ajax II", "away": "AZ II", "home_goals": 3, "away_goals": 0}
        result = reconcile([primary, {**primary, "home": "AZ II", "away": "Ajax II"}],
                           {"knvb": results, "vi": other})
        self.assertEqual({"CONFLICT": 1, "UNMATCHED": 1}, result["counts"])
        self.assertFalse(result["upstream_lineage_certified"])

    def test_ambiguous_normalized_source_identity_is_never_attached(self):
        match = {"league": "fr.1", "date": "2026-11-23", "home": "Example", "away": "Other",
                 "home_goals": 3, "away_goals": 0}
        official = {**match, "home": "Example FC", "official_score": [3, 0], "proof": "official"}
        ledger = {"queues": {"newer": {"provisional_matches": [match]}}}
        result = audit(ledger, {"fixtures": [official]})
        self.assertEqual({"OFFICIAL_RESULT_CORROBORATION_ONLY": 1}, result["counts"])
        result = audit(ledger, {"fixtures": [official, {**official, "home": "FC Example"}]})
        self.assertEqual({"UPSTREAM_LINEAGE_UNPROVEN": 1}, result["counts"])
        self.assertFalse(result["ex_final_allowed"])
