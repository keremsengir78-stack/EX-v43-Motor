"""EX v4.3 fail-closed final authorization boundary.

Metadata gates are useful for data hygiene but cannot confer real-world source
verification. No caller-supplied Boolean may authorize EX FINAL.
"""


import math


def _calibration_measured(report):
    return (isinstance(report, dict)
            and report.get("status") == "AUDIT_COMPLETE_NOT_CALIBRATED"
            and isinstance(report.get("sample_size"), int)
            and not isinstance(report.get("sample_size"), bool)
            and report["sample_size"] >= 30
            and all(isinstance(report.get(key), (int, float))
                    and not isinstance(report.get(key), bool)
                    and math.isfinite(report[key])
                    and 0 <= report[key] <= 1
                    for key in ("brier_score", "expected_calibration_error",
                                "maximum_calibration_error")))


def _historical_measured(report):
    return (isinstance(report, dict)
            and report.get("status") == "OUT_OF_SAMPLE_AUDIT_COMPLETE_NOT_CERTIFIED"
            and isinstance(report.get("split"), dict)
            and report["split"].get("status") == "CHRONOLOGICAL_SPLIT_READY"
            and _calibration_measured(report.get("evaluation")))


def evaluate_final_readiness(provenance_pipeline, calibration_audit=None,
                             historical_validation=None):
    issues = []
    if not isinstance(provenance_pipeline, dict):
        issues.append("pipeline:missing")
    elif provenance_pipeline.get("status") != "RECONCILED_WITH_METADATA_UNVERIFIED":
        issues.append("pipeline:blocked")
    if not isinstance(calibration_audit, dict):
        issues.append("calibration:missing")
    elif not _calibration_measured(calibration_audit):
        issues.append("calibration:unavailable")
    if not isinstance(historical_validation, dict):
        issues.append("historical_validation:missing")
    elif not _historical_measured(historical_validation):
        issues.append("historical_validation:unavailable")
    # Neither a matching provider result nor a caller-supplied assertion proves
    # independent external source inspection. There is currently no verified
    # evidence retrieval implementation in this repository.
    issues.append("external_evidence:verification_not_implemented")
    checks = {
        "source_pipeline": isinstance(provenance_pipeline, dict)
        and provenance_pipeline.get("status") == "RECONCILED_WITH_METADATA_UNVERIFIED",
        "calibration": isinstance(calibration_audit, dict)
        and _calibration_measured(calibration_audit),
        "historical_validation": isinstance(historical_validation, dict)
        and _historical_measured(historical_validation),
        "external_evidence": False,
    }
    return {"status": "BLOCKED", "issues": issues,
            "checks": checks,
            "missing_checks": [name for name, passed in checks.items() if not passed],
            "externally_verified": False, "ex_final_allowed": False}
