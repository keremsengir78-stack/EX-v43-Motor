"""EX v4.3 fail-closed final authorization boundary.

Metadata gates are useful for data hygiene but cannot confer real-world source
verification. No caller-supplied Boolean may authorize EX FINAL.
"""


import math
import datetime as dt


def _calibration_bins_consistent(report):
    try:
        bins = report["reliability_bins"]
        total = report["sample_size"]
        ece = sum(row["count"] * abs(row["mean_predicted"] - row["observed_rate"])
                  for row in bins) / total
        mce = max(abs(row["mean_predicted"] - row["observed_rate"])
                  for row in bins)
        mean_prediction = sum(row["count"] * row["mean_predicted"]
                              for row in bins) / total
        observed = sum(row["count"] * row["observed_rate"]
                       for row in bins) / total
        return (abs(ece - report["expected_calibration_error"]) <= 1e-6
                and abs(mce - report["maximum_calibration_error"]) <= 1e-6
                and abs(mean_prediction - report["mean_predicted"]) <= 1e-6
                and abs(observed - report["observed_rate"]) <= 1e-6)
    except (KeyError, TypeError, ValueError, ZeroDivisionError, OverflowError):
        return False


def _calibration_measured(report):
    return (isinstance(report, dict)
            and report.get("status") == "AUDIT_COMPLETE_NOT_CALIBRATED"
            and isinstance(report.get("sample_size"), int)
            and not isinstance(report.get("sample_size"), bool)
            and report["sample_size"] >= 30
            and isinstance(report.get("reliability_bins"), list)
            and bool(report["reliability_bins"])
            and all(isinstance(row, dict)
                    and isinstance(row.get("count"), int)
                    and not isinstance(row.get("count"), bool)
                    and row["count"] > 0
                    and all(isinstance(row.get(key), (int, float))
                            and not isinstance(row.get(key), bool)
                            and math.isfinite(row[key])
                            and 0 <= row[key] <= 1
                            for key in ("mean_predicted", "observed_rate"))
                    for row in report["reliability_bins"])
            and sum(row["count"] for row in report["reliability_bins"])
            == report["sample_size"]
            and _calibration_bins_consistent(report)
            and all(isinstance(report.get(key), (int, float))
                    and not isinstance(report.get(key), bool)
                    and math.isfinite(report[key])
                    and 0 <= report[key] <= 1
                    for key in ("brier_score", "expected_calibration_error",
                                "maximum_calibration_error")))


def _holdout_records_consistent(report):
    try:
        split = report["split"]
        rows = split["test"]
        evaluation = report["evaluation"]
        if not isinstance(rows, list) or len(rows) != evaluation["sample_size"]:
            return False

        def utc(value):
            if not isinstance(value, str) or not value.endswith("Z"):
                raise ValueError("UTC Z timestamp required")
            result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if result.utcoffset() != dt.timedelta(0):
                raise ValueError("non-UTC timestamp")
            return result

        boundary = utc(split["evaluation_start"])
        seen = set()
        probabilities = []
        outcomes = []
        for row in rows:
            if not isinstance(row, dict):
                return False
            fixture = row.get("fixture_id")
            if not isinstance(fixture, str) or not fixture.strip() or fixture in seen:
                return False
            seen.add(fixture)
            if row.get("market") != evaluation.get("market"):
                return False
            probability = row.get("probability")
            outcome = row.get("outcome")
            if (isinstance(probability, bool)
                    or not isinstance(probability, (int, float))
                    or not math.isfinite(probability)
                    or not 0 <= probability <= 1
                    or type(outcome) is not int or outcome not in (0, 1)):
                return False
            predicted = utc(row["predicted_at"])
            kickoff = utc(row["kickoff_at"])
            settled = utc(row["settled_at"])
            if not (boundary <= predicted < kickoff < settled):
                return False
            probabilities.append(probability)
            outcomes.append(outcome)

        training = split.get("train")
        if not isinstance(training, list):
            return False
        training_ids = set()
        for row in training:
            if not isinstance(row, dict):
                return False
            fixture = row.get("fixture_id")
            if not isinstance(fixture, str) or not fixture.strip() or fixture in training_ids:
                return False
            if fixture in seen or row.get("market") != evaluation.get("market"):
                return False
            if not utc(row["settled_at"]) < boundary:
                return False
            training_ids.add(fixture)

        count = len(rows)
        brier = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / count
        return (abs(sum(probabilities) / count - evaluation["mean_predicted"]) <= 1e-6
                and abs(sum(outcomes) / count - evaluation["observed_rate"]) <= 1e-6
                and abs(brier - evaluation["brier_score"]) <= 1e-6)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, ZeroDivisionError):
        return False


def _historical_measured(report):
    return (isinstance(report, dict)
            and report.get("status") == "OUT_OF_SAMPLE_AUDIT_COMPLETE_NOT_CERTIFIED"
            and isinstance(report.get("split"), dict)
            and report["split"].get("status") == "CHRONOLOGICAL_SPLIT_READY"
            and isinstance(report["split"].get("test"), list)
            and _holdout_records_consistent(report)
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
