"""Reviewed, code-owned calibration registrations for the EX v4.3 score."""
import math

from ex_calibration_audit import audit_predictions, canonical_utc
from ex_component_experiment import weekly_interval
from ex_final_readiness import _historical_measured
from ex_leagues import APPROVED_LEAGUES

MODEL_VERSION = "EX-v4.3-50-30-20"


def probability(value):
    return type(value) in (float, int) and 0 <= value <= 1


def mapping(score, intercept, slope):
    value = intercept + slope * score
    return 1 / (1 + math.exp(-value)) if value >= 0 else math.exp(value) / (1 + math.exp(value))


def validate_registration(entry, market):
    """Recompute chronological holdout and paired reference results on review."""
    try:
        audit = entry["holdout"]
        split = audit["split"]
        leagues = set(entry["competitions"])
        fit_at = canonical_utc(entry["frozen_at"])
        approved_at = canonical_utc(entry["approved_at"])
        if (entry["model_version"] != MODEL_VERSION or not entry["id"] or entry["market"] != market
                or not leagues or not leagues <= APPROVED_LEAGUES.keys()
                or not entry["independent_review"].startswith("https://")
                or not _historical_measured(audit) or audit["evaluation"]["market"] != market
                or not fit_at <= canonical_utc(split["evaluation_start"]) < approved_at):
            return False
        a, b = entry["coefficients"]
        if any(type(x) not in (float, int) or not math.isfinite(x) for x in (a, b)) or b <= 0:
            return False
        for row in split["train"]:
            if row["competition"] not in leagues or canonical_utc(row["settled_at"]) >= fit_at:
                return False
        test = split["test"]
        if {r["competition"] for r in test} != leagues:
            return False
        if any(not probability(r["reference_probability"]) or not probability(r["weighted_score"])
               or abs(mapping(r["weighted_score"], a, b) - r["probability"]) > 1e-8 for r in test):
            return False
        candidate = audit_predictions(test, market, entry["approved_at"])
        reference = audit_predictions([{**r, "probability": r["reference_probability"]} for r in test],
                                      market, entry["approved_at"])
        if candidate["issues"] or reference["issues"]:
            return False
        interval = weekly_interval(
            [(canonical_utc(r["kickoff_at"]).date(),) for r in test],
            [(r["reference_probability"] - r["outcome"]) ** 2 for r in test],
            [(r["probability"] - r["outcome"]) ** 2 for r in test],
        )
        return (interval is not None and interval[1] < 0
                and candidate["log_loss"] <= reference["log_loss"]
                and candidate["expected_calibration_error"] <= reference["expected_calibration_error"])
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return False
