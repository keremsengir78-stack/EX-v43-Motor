"""EX v4.3 venue-aware historical evidence, strictly pre-match.

Input consists of dated, verified match records; scores are descriptive metrics,
never calibrated event probabilities. The last-five window intentionally overlaps
the last-ten window under the user-approved 40/30/20/10 weighting.
"""
import datetime as dt
import math

WINDOW_WEIGHTS = (("venue_last5", 5, 0.40), ("venue_last10", 10, 0.30),
                  ("current_season", None, 0.20), ("previous_venue", None, 0.10))


def historical_metric(windows, as_of, metric="goals_for"):
    issues = []
    try:
        if not isinstance(as_of, str) or not as_of.endswith("Z"):
            raise ValueError("UTC cutoff required")
        cutoff = dt.datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if cutoff.tzinfo is None:
            raise ValueError("timezone missing")
    except (TypeError, ValueError, OverflowError):
        return {"status": "BLOCKED", "issues": ["as_of:invalid"],
                "weighted_metric": None, "components": {}, "ex_final_allowed": False}
    if not isinstance(windows, dict):
        windows = {}
    components = {}
    for name, required, weight in WINDOW_WEIGHTS:
        rows = windows.get(name)
        if not isinstance(rows, list) or not rows or (required is not None and len(rows) != required):
            issues.append(name + ":sample_incomplete")
            continue
        seen = set()
        values = []
        dates = []
        for i, item in enumerate(rows):
            if not isinstance(item, dict):
                issues.append(name + ":record_invalid")
                continue
            identifier = item.get("fixture_id")
            if not isinstance(identifier, str) or not identifier.strip() or identifier in seen:
                issues.append(name + ":fixture_duplicate_or_missing")
            else:
                seen.add(identifier)
            if item.get("verified") is not True or not isinstance(item.get("source"), str) or not item["source"].strip():
                issues.append(name + ":source_unverified")
            value = item.get(metric)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                issues.append(name + ":metric_invalid")
            else:
                values.append(float(value))
            try:
                stamp = item["kickoff_at"]
                if not isinstance(stamp, str) or not stamp.endswith("Z"):
                    raise ValueError("UTC required")
                when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if when.tzinfo is None or when >= cutoff:
                    raise ValueError("future match")
                dates.append(when)
            except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
                issues.append(name + ":date_invalid_or_future")
        if len(dates) == len(rows) and dates != sorted(dates, reverse=True):
            issues.append(name + ":not_latest_first")
        if len(values) == len(rows):
            mean = sum(values) / len(values)
            components[name] = {"count": len(rows), "mean": round(mean, 8),
                                "weight": weight, "contribution": round(mean * weight, 8)}
    # The five most recent venue fixtures must match the first five of the ten.
    five = windows.get("venue_last5")
    ten = windows.get("venue_last10")
    if isinstance(five, list) and isinstance(ten, list) and len(five) == 5 and len(ten) == 10:
        if [x.get("fixture_id") if isinstance(x, dict) else None for x in five] != [
                x.get("fixture_id") if isinstance(x, dict) else None for x in ten[:5]]:
            issues.append("venue_windows:inconsistent")
    return {"status": "HISTORICAL_EVIDENCE_ONLY" if not issues else "BLOCKED",
            "issues": sorted(set(issues)),
            "weighted_metric": round(sum(x["contribution"] for x in components.values()), 8)
                               if not issues else None,
            "components": components if not issues else {},
            "calibrated_probability": None, "ex_final_allowed": False}
