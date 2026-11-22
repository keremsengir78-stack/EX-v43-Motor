"""Join immutable pre-match prediction records with independently settled outcomes.

A join never creates missing predictions or converts realized outcomes into
probabilities. Audit remains descriptive and never enables EX FINAL.
"""
import datetime as dt
import math

from ex_calibration_audit import audit_predictions, MARKETS
from ex_market_outcomes import market_outcomes


def join_calibration_records(predictions, fixtures, market, as_of, min_samples=100):
    issues = []
    if not isinstance(market, str) or market not in MARKETS:
        return {"status": "BLOCKED", "issues": ["market:unsupported"],
                "joined_records": [], "audit": None,
                "calibration_certified": False, "ex_final_allowed": False}
    if isinstance(min_samples, bool) or not isinstance(min_samples, int) or min_samples < 30:
        return {"status": "BLOCKED", "issues": ["min_samples:invalid"],
                "joined_records": [], "audit": None,
                "calibration_certified": False, "ex_final_allowed": False}
    outcome_result = market_outcomes(fixtures, as_of)
    if outcome_result["status"] != "OUTCOMES_READY":
        issues.extend("outcome:" + x for x in outcome_result["issues"])
    if not isinstance(predictions, list) or not predictions:
        issues.append("predictions:missing")
        predictions = []
    outcome_map = {x["fixture_id"]: x for x in outcome_result["outcomes"]}
    seen = set()
    joined = []
    for i, row in enumerate(predictions):
        if not isinstance(row, dict):
            issues.append("prediction:%d:invalid" % i)
            continue
        fid = row.get("fixture_id")
        if not isinstance(fid, str) or not fid.strip() or fid in seen:
            issues.append("prediction:%d:duplicate_or_missing_fixture" % i)
            continue
        seen.add(fid)
        if row.get("market") != market:
            issues.append("prediction:%d:market_mismatch" % i)
        outcome = outcome_map.get(fid)
        if outcome is None:
            issues.append("prediction:%d:outcome_missing" % i)
            continue
        if row.get("kickoff_at") != outcome["kickoff_at"]:
            issues.append("prediction:%d:kickoff_mismatch" % i)
        if row.get("verified") is not True or not isinstance(row.get("source"), str) or not row["source"].strip():
            issues.append("prediction:%d:unverified" % i)
        probability = row.get("probability")
        if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not math.isfinite(probability) or not 0 <= probability <= 1:
            issues.append("prediction:%d:probability_invalid" % i)
            continue
        try:
            stamp = row["predicted_at"]
            if not isinstance(stamp, str) or not stamp.endswith("Z"):
                raise ValueError("UTC prediction required")
            predicted = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            kickoff = dt.datetime.fromisoformat(outcome["kickoff_at"].replace("Z", "+00:00"))
            if (predicted.utcoffset() != dt.timedelta(0)
                    or kickoff.utcoffset() != dt.timedelta(0)
                    or predicted >= kickoff):
                raise ValueError("leakage")
        except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
            issues.append("prediction:%d:temporal_leakage" % i)
            continue
        settled = row.get("settled_at")
        try:
            if not isinstance(settled, str) or not settled.endswith("Z"):
                raise ValueError("UTC settlement required")
            settlement = dt.datetime.fromisoformat(settled.replace("Z", "+00:00"))
            if settlement.utcoffset() != dt.timedelta(0) or settlement <= kickoff:
                raise ValueError("settlement before kickoff")
        except (ValueError, TypeError, OverflowError):
            issues.append("prediction:%d:settlement_invalid" % i)
            continue
        joined.append({"fixture_id": fid, "market": market, "probability": probability,
                       "outcome": outcome[market], "predicted_at": stamp,
                       "kickoff_at": outcome["kickoff_at"], "settled_at": settled})
    if seen != set(outcome_map):
        issues.append("predictions:fixture_coverage_incomplete")
    if issues:
        return {"status": "BLOCKED", "issues": sorted(set(issues)), "joined_records": [],
                "audit": None, "calibration_certified": False, "ex_final_allowed": False}
    audit = audit_predictions(joined, market, as_of, min_samples=min_samples)
    return {"status": audit["status"], "issues": audit["issues"],
            "joined_records": joined, "audit": audit,
            "calibration_certified": False, "ex_final_allowed": False}
