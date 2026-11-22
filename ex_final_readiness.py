"""EX v4.3 fail-closed final authorization boundary.

Metadata gates are useful for data hygiene but cannot confer real-world source
verification. No caller-supplied Boolean may authorize EX FINAL.
"""


def evaluate_final_readiness(provenance_pipeline, calibration_audit=None,
                             historical_validation=None):
    issues = []
    if not isinstance(provenance_pipeline, dict):
        issues.append("pipeline:missing")
    elif provenance_pipeline.get("status") != "RECONCILED_WITH_METADATA_UNVERIFIED":
        issues.append("pipeline:blocked")
    if not isinstance(calibration_audit, dict):
        issues.append("calibration:missing")
    elif calibration_audit.get("status") in (None, "BLOCKED"):
        issues.append("calibration:unavailable")
    if not isinstance(historical_validation, dict):
        issues.append("historical_validation:missing")
    elif historical_validation.get("status") in (None, "BLOCKED"):
        issues.append("historical_validation:unavailable")
    # Neither a matching provider result nor a caller-supplied assertion proves
    # independent external source inspection. There is currently no verified
    # evidence retrieval implementation in this repository.
    issues.append("external_evidence:verification_not_implemented")
    checks = {
        "source_pipeline": isinstance(provenance_pipeline, dict)
        and provenance_pipeline.get("status") == "RECONCILED_WITH_METADATA_UNVERIFIED",
        "calibration": isinstance(calibration_audit, dict)
        and calibration_audit.get("status") not in (None, "BLOCKED"),
        "historical_validation": isinstance(historical_validation, dict)
        and historical_validation.get("status") not in (None, "BLOCKED"),
        "external_evidence": False,
    }
    return {"status": "BLOCKED", "issues": issues,
            "checks": checks,
            "missing_checks": [name for name, passed in checks.items() if not passed],
            "externally_verified": False, "ex_final_allowed": False}
