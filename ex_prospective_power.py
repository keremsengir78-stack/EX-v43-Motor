"""Paired weekly loss inference at a preregistered, fixed evaluation date."""

import math
from statistics import NormalDist, mean, stdev


def plan(pilot, delta, alpha, power, comparisons):
    """Return a planning approximation in independent weekly blocks."""
    if (type(comparisons) is not int or comparisons < 1 or not 0 < delta <= 1
            or not 0 < alpha < .5 or not .5 < power < 1):
        raise ValueError("Invalid prospective design")
    if len(pilot) < 2 or any(type(x) not in (float, int) or not math.isfinite(x)
                             or abs(x) > 1 for x in pilot):
        raise ValueError("Two or more valid independent pilot blocks required")
    sigma = stdev(pilot)
    if sigma <= 0:
        raise ValueError("Pilot dispersion is unidentified with constant block differences")
    normal = NormalDist()
    per_test = alpha / comparisons
    # Bonferroni-adjusted one-sided test of the smallest worthwhile paired Brier gain.
    n = math.ceil(((normal.inv_cdf(1 - per_test) + normal.inv_cdf(power)) * sigma / delta)**2)
    guaranteed = math.ceil(2 * (math.sqrt(math.log(1 / per_test)) + math.sqrt(math.log(1 / (1 - power))))**2
                           / delta**2)
    return {"required_weeks": max(2, n), "bounded_power_weeks": guaranteed, "pilot_sd": sigma, "pilot_mean": mean(pilot),
            "target_gain": delta, "family_alpha": alpha, "per_test_alpha": per_test,
            "design_power": power, "comparisons": comparisons, "unit": "PAIRED_WEEK_BLOCK",
            "method": "NORMAL_PLANNING_APPROXIMATION"}


def verdict(weekly_deltas, design):
    """Conservative Hoeffding bound for independent weekly means in [-1, 1]."""
    n = len(weekly_deltas)
    if n < design["required_weeks"]:
        return {"status": "INSUFFICIENT_WEEKS", "weeks": n, "research_supported": False}
    if any(not math.isfinite(x) or not -1 <= x <= 1 for x in weekly_deltas):
        raise ValueError("Invalid weekly paired loss difference")
    final_mean = mean(weekly_deltas)
    upper = final_mean + math.sqrt(2 * math.log(1 / design["per_test_alpha"]) / n)
    return {"status": "EVALUATED", "weeks": n, "mean_brier_delta": final_mean, "upper_bound": upper,
            "research_supported": upper < 0 and final_mean <= -design["target_gain"],
            "production_allowed": False}
