"""Chronological calibration experiment for retrospective baseline forecasts."""

import math
from statistics import mean


def chronological_intercept(records):
    """Fit a log-odds intercept on earlier matches and compare on later dates."""
    days = sorted({day for day, _, _ in records})
    blocked = {"status": "INSUFFICIENT_CHRONOLOGICAL_SAMPLE", "calibration_certified": False}
    if len(days) < 2:
        return blocked
    boundary = days[len(days) * 7 // 10]
    train = [(p, y) for day, p, y in records if day < boundary]
    test = [(p, y) for day, p, y in records if day >= boundary]
    if min(len(train), len(test)) < 30 or len({y for _, y in train}) != 2:
        return blocked

    def adjusted(probability, shift):
        p = min(1 - 1e-6, max(1e-6, probability))
        return 1 / (1 + math.exp(-(math.log(p / (1 - p)) + shift)))

    lower, upper = -20.0, 20.0
    frequency = mean(y for _, y in train)
    for _ in range(60):
        middle = (lower + upper) / 2
        if mean(adjusted(p, middle) for p, _ in train) < frequency:
            lower = middle
        else:
            upper = middle
    shift = (lower + upper) / 2
    baseline = mean((p - y) ** 2 for p, y in test)
    corrected = mean((adjusted(p, shift) - y) ** 2 for p, y in test)
    return {
        "status": "HOLDOUT_IMPROVED" if corrected < baseline else "HOLDOUT_NOT_IMPROVED",
        "train_n": len(train), "test_n": len(test), "holdout_start_date": boundary.isoformat(),
        "baseline_brier": baseline, "adjusted_brier": corrected, "training_log_odds_intercept": shift,
        "calibration_certified": False, "forecast_provenance": "RETROSPECTIVE_BASELINE",
    }
