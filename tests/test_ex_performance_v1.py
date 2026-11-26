import unittest
from unittest.mock import patch

from ex_history_archive import utc
from ex_performance_v1 import History, score_model, replay


class PerformanceV1Tests(unittest.TestCase):
    def test_low_score_adjustment_conserves_mass_and_separates_markets(self):
        baseline = score_model(1.5, 1.2, 0)
        revised = score_model(1.5, 1.2, -.08)
        self.assertAlmostEqual(1., revised["probability_mass"])
        self.assertAlmostEqual(baseline["over25"], revised["over25"])
        self.assertGreater(revised["btts"], baseline["btts"])
        self.assertAlmostEqual(baseline["score_scenarios"]["3-0"], revised["score_scenarios"]["3-0"])
        self.assertGreater(revised["one_side_three_plus"], revised["score_scenarios"]["3-0"])

    def test_replay_excludes_results_settled_at_cutoff_and_later(self):
        cutoff = utc("2026-11-25T17:45:00Z")
        earlier = {"event_id": "1", "kickoff": utc("2026-11-24T10:00:00Z"),
                   "finished": utc("2026-11-24T12:00:00Z"), "score": (1, 0)}
        simultaneous = {**earlier, "event_id": "2", "finished": cutoff}
        target = {"event_id": "3", "kickoff": cutoff, "finished": utc("2026-11-25T20:00:00Z"), "score": (0, 4)}
        with patch.object(History, "update") as update, patch.object(History, "features", return_value=True):
            self.assertEqual([(target, True)], list(replay([earlier, simultaneous, target], [target])))
        update.assert_called_once_with(earlier)
