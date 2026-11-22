"""EX v4.3 probability calibration audit, without automatic FINAL promotion.

All records must be settled historical out-of-sample predictions. This module
measures calibration; it does not train a model or certify a market.
"""
import datetime as dt
import math

MARKETS = ("2.5_UST", "KG_VAR", "MS1", "MS2")


def audit_predictions(records, market, cutoff, min_samples=100):
    issues = []
    if market not in MARKETS:
        issues.append("market:unsupported")
    if isinstance(min_samples, bool) or not isinstance(min_samples, int) or min_samples < 30:
        issues.append("min_samples:invalid")
    try:
        if not isinstance(cutoff, str) or not cutoff.endswith("Z"):
            raise ValueError("UTC cutoff required")
        boundary = dt.datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
    except (ValueError, TypeError, OverflowError):
        boundary = None
        issues.append("cutoff:invalid")
    if not isinstance(records, list) or not records:
        issues.append("records:missing")
        records = []
    seen = set()
    scores = []
    for i, record in enumerate(records):
        if not isinstance(record, dict):
            issues.append("record:%d:invalid" % i)
            continue
        identifier = record.get("fixture_id")
        if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
            issues.append("record:%d:duplicate_or_missing_fixture" % i)
        else:
            seen.add(identifier)
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
            predicted = dt.datetime.fromisoformat(record["predicted_at"].replace("Z", "+00:00"))
            kickoff = dt.datetime.fromisoformat(record["kickoff_at"].replace("Z", "+00:00"))
            settled = dt.datetime.fromisoformat(record["settled_at"].replace("Z", "+00:00"))
            if any(t.tzinfo is None or t.utcoffset() is None for t in (predicted, kickoff, settled)):
                raise ValueError("timezone required")
            if not (predicted < kickoff < settled) or (boundary is not None and settled >= boundary):
                issues.append("record:%d:temporal_leakage" % i)
        except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
            issues.append("record:%d:invalid_timestamp" % i)
        scores.append((probability - outcome) ** 2)
    if not issues and len(scores) < min_samples:
        issues.append("sample:insufficient")
    bins = []
    if not issues:
        for low in range(0, 100, 10):
            selected = [
                (record["probability"], record["outcome"])
                for record in records
                if low / 100 <= record["probability"] < (low + 10) / 100
                or (low == 90 and record["probability"] == 1)
            ]
            if selected:
                bins.append({
                    "range": "%02d-%02d" % (low, low + 10),
                    "count": len(selected),
                    "mean_predicted": round(sum(p for p, _ in selected) / len(selected), 8),
                    "observed_rate": round(sum(y for _, y in selected) / len(selected), 8),
                })
    mean_predicted = (round(sum(record["probability"] for record in records) / len(records), 8)
                      if not issues else None)
    observed_rate = (round(sum(record["outcome"] for record in records) / len(records), 8)
                     if not issues else None)
    return {
        "status": "AUDIT_COMPLETE_NOT_CALIBRATED" if not issues else "BLOCKED",
        "market": market,
        "sample_size": len(scores),
        "brier_score": round(sum(scores) / len(scores), 8) if scores and not issues else None,
        "issues": issues,
        "reliability_bins": bins,
        "mean_predicted": mean_predicted,
        "observed_rate": observed_rate,
        "calibration_certified": False,
        "pup_allowed": False,
        "ex_final_allowed": False,
    }
