"""EX v4.3 probability calibration audit, without automatic FINAL promotion.

All records must be settled historical out-of-sample predictions. This module
measures calibration; it does not train a model or certify a market.
"""
import datetime as dt
import math
import re

MARKETS = ("2.5_UST", "KG_VAR", "MS1", "MS2")
UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def canonical_utc(value):
    if not isinstance(value, str) or UTC_TIMESTAMP.fullmatch(value) is None:
        raise ValueError("canonical UTC timestamp required")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("UTC timestamp required")
    return parsed


def audit_predictions(records, market, cutoff, min_samples=100):
    issues = []
    if not isinstance(market, str) or market not in MARKETS:
        issues.append("market:unsupported")
    if isinstance(min_samples, bool) or not isinstance(min_samples, int) or min_samples < 30:
        issues.append("min_samples:invalid")
        min_samples = 30
    try:
        boundary = canonical_utc(cutoff)
    except (ValueError, TypeError, OverflowError):
        boundary = None
        issues.append("cutoff:invalid")
    if not isinstance(records, list) or not records:
        issues.append("records:missing")
        records = []
    seen = set()
    scores = []
    log_losses = []
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            issues.append("record:%d:invalid" % i)
            continue
        identifier = record.get("fixture_id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier.strip() in seen:
            issues.append("record:%d:duplicate_or_missing_fixture" % i)
        else:
            seen.add(identifier.strip())
        if record.get("market") != market:
            issues.append("record:%d:market_mismatch" % i)
        probability = record.get("probability")
        outcome = record.get("outcome")
        if (isinstance(probability, bool) or not isinstance(probability, (int, float))
                or not math.isfinite(probability) or not 0 <= probability <= 1
                or isinstance(outcome, bool) or outcome not in (0, 1)
                or not isinstance(outcome, int)):
            issues.append("record:%d:invalid_prediction_or_outcome" % i)
            continue
        try:
            timestamps = [record[key] for key in ("predicted_at", "kickoff_at", "settled_at")]
            predicted, kickoff, settled = [canonical_utc(value) for value in timestamps]
            if not (predicted < kickoff < settled) or (boundary is not None and settled >= boundary):
                issues.append("record:%d:temporal_leakage" % i)
        except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
            issues.append("record:%d:invalid_timestamp" % i)
        scores.append((probability - outcome) ** 2)
        # Clamp only for logarithms: retain the original probability for Brier/ECE.
        safe_probability = min(max(float(probability), 1e-15), 1 - 1e-15)
        log_losses.append(-(outcome * math.log(safe_probability) +
                            (1 - outcome) * math.log1p(-safe_probability)))
    if not issues and len(scores) < min_samples:
        issues.append("sample:insufficient")
    bins = []
    if not issues:
        grouped = {}
        for record in records:
            low = min(int(record["probability"] * 10), 9) * 10
            grouped.setdefault(low, []).append(
                (record["probability"], record["outcome"]))
        for low in sorted(grouped):
            selected = grouped[low]
            if selected:
                bins.append({
                    "range": "%02d-%02d" % (low, low + 10),
                    "count": len(selected),
                    "mean_predicted": round(sum(p for p, _ in selected) / len(selected), 8),
                    "observed_rate": round(sum(y for _, y in selected) / len(selected), 8),
                })
    expected_calibration_error = (
        round(sum(
            item["count"] * abs(item["mean_predicted"] - item["observed_rate"])
            for item in bins
        ) / len(records), 8)
        if not issues else None
    )
    maximum_calibration_error = (
        round(max(abs(item["mean_predicted"] - item["observed_rate"]) for item in bins), 8)
        if not issues else None
    )
    mean_predicted = (round(sum(record["probability"] for record in records) / len(records), 8)
                      if not issues else None)
    observed_rate = (round(sum(record["outcome"] for record in records) / len(records), 8)
                     if not issues else None)
    return {
        "status": "AUDIT_COMPLETE_NOT_CALIBRATED" if not issues else "BLOCKED",
        "market": market,
        "sample_size": len(scores),
        "brier_score": round(sum(scores) / len(scores), 8) if scores and not issues else None,
        "log_loss": round(sum(log_losses) / len(log_losses), 8)
                    if log_losses and not issues else None,
        "issues": issues,
        "reliability_bins": bins,
        "expected_calibration_error": expected_calibration_error,
        "maximum_calibration_error": maximum_calibration_error,
        "mean_predicted": mean_predicted,
        "observed_rate": observed_rate,
        "calibration_certified": False,
        "pup_allowed": False,
        "ex_final_allowed": False,
    }
