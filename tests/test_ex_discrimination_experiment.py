from datetime import datetime, timedelta, timezone
import unittest

from ex_discrimination_experiment import as_markets, features
from ex_performance_v1 import score_model
from ex_research_scorelines import reconcile


class DiscriminationTests(unittest.TestCase):
    def test_archived_feature_cannot_use_later_observation(self):
        start = datetime(2026, 9, 1, tzinfo=timezone.utc)
        teams = {"home": "1", "away": "2"}
        facts = [{"event_id": str(i), "competition": "eng.1", "teams": teams,
                  "kickoff": start + timedelta(days=i), "score": (2, 1),
                  "finished": start + timedelta(days=i, hours=2),
                  "captured_at": start + timedelta(days=i, hours=3)}
                 for i in range(30)]
        cutoff = start + timedelta(days=31)
        target = {"event_id": "future", "competition": "eng.1", "teams": teams,
                  "kickoff": cutoff + timedelta(hours=4), "as_of": cutoff}
        known = dict(features(facts, [target], archived=True))
        self.assertIn("future", known)
        facts[-1]["captured_at"] = cutoff
        self.assertEqual({}, dict(features(facts, [target], archived=True)))
        self.assertEqual(known, dict(features(facts, [target])))

    def test_score_model_marginals_match_probability_axioms(self):
        grid = score_model(1.9, 1.3, -.12)
        self.assertAlmostEqual(1, grid["probability_mass"])
        self.assertEqual("FEASIBLE", reconcile(as_markets(grid))["status"])
