"""EX v4.3 historical-to-decision evidence orchestration.

Keeps raw venue metrics separate from dimensionless EX-G scores. No implicit
normalization or probability conversion is permitted.
"""
from ex_historical_samples import historical_metric
from ex_decision import weighted_evidence, MARKETS


def prepare_market_evidence(market, historical_windows, feature_scores, as_of):
    if market not in MARKETS:
        return {"status": "BLOCKED", "issues": ["market:unsupported"],
                "historical": None, "decision": None, "ex_final_allowed": False}
    if not isinstance(historical_windows, dict):
        historical_windows = {}
    historical = {
        metric: historical_metric(historical_windows, as_of, metric=metric)
        for metric in ("goals_for", "goals_against")
    }
    decision = weighted_evidence(feature_scores, as_of=as_of)
    issues = []
    for metric, result in historical.items():
        if result["status"] != "HISTORICAL_EVIDENCE_ONLY":
            issues.extend("historical:" + metric + ":" + issue for issue in result["issues"])
    if decision["status"] != "EVIDENCE_COMPLETE_UNCALIBRATED":
        issues.extend("decision:" + issue for issue in decision["issues"])
    return {
        "status": "EVIDENCE_READY_UNCALIBRATED" if not issues else "BLOCKED",
        "market": market,
        "historical": historical,
        "decision": decision,
        "issues": issues,
        "calibrated_probability": None,
        "pup_allowed": False,
        "ex_final_allowed": False,
    }
