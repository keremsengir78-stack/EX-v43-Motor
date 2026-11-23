"""Include root-level calibration safety cases in the full CI discovery suite.

The workflow discovers tests/test*.py; the canonical regression cases live
at repository root. Importing the TestCase exposes all cases to discovery.
"""
from test_ex_calibration_safety import CalibrationSafetyTests  # noqa: F401
