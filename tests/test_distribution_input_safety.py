"""Regression guards for EX baseline goal-intensity inputs."""
import math
import unittest
from ex_engine import distribution


class DistributionInputSafetyTests(unittest.TestCase):
    def test_invalid_intensities_fail_closed(self):
        for invalid in (float("nan"), float("inf"), -0.1, 5.1, True, None, "1.2"):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(ValueError):
                    distribution(invalid, 1.0)
                with self.assertRaises(ValueError):
                    distribution(1.0, invalid)

    def test_valid_intensities_are_bounded(self):
        for lh, la in ((0, 0), (0.05, 0.05), (1.2, 1.5), (5, 5)):
            with self.subTest(lh=lh, la=la):
                report = distribution(lh, la)
                for key in ("over25", "btts", "home_win", "draw", "away_win", "probability_mass"):
                    self.assertTrue(math.isfinite(report[key]))
                    self.assertGreaterEqual(report[key], 0)
                    self.assertLessEqual(report[key], 1.00000001)


if __name__ == "__main__":
    unittest.main()
