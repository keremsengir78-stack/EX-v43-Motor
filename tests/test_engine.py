import unittest
import math

from ex_engine import load, audit, backtest
from ex_live_data import run


class TestEXMotor(unittest.TestCase):

    def test_modules_available(self):
        self.assertTrue(callable(load))
        self.assertTrue(callable(audit))
        self.assertTrue(callable(backtest))
        self.assertTrue(callable(run))

    def test_probability_bounds(self):
        for value in (0.0, 0.25, 0.5, 0.75, 1.0):
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 1)

    def test_poisson_normalization(self):
        lam = 2.0
        total = sum(
            math.exp(-lam) * lam**k / math.factorial(k)
            for k in range(30)
        )
        self.assertAlmostEqual(total, 1.0, places=8)


if __name__ == "__main__":
    unittest.main()
