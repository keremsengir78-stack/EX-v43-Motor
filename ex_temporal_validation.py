"""EX v4.3 chronological out-of-sample split guard.

Strictly separates training settlement from evaluation prediction time.
Does not train, calibrate or certify a model.
"""
import datetime as dt


def _timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("UTC timestamp required")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("UTC timezone required")
    return parsed


def chronological_split(records, evaluation_start, min_train=30, min_test=30):
    issues = []
    try:
        boundary = _timestamp(evaluation_start)
    except (TypeError, ValueError, OverflowError):
        return {"status": "BLOCKED", "issues": ["evaluation_start:invalid"],
                "train": [], "test": [], "ex_final_allowed": False}
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 1
           for x in (min_train, min_test)):
        issues.append("sample_threshold:invalid")
        min_train = 30
        min_test = 30
    if not isinstance(records, list) or not records:
        issues.append("records:missing")
        records = []
    train, test = [], []
    seen = set()
    for i, row in enumerate(records):
        if not isinstance(row, dict):
            issues.append("record:%d:invalid" % i)
            continue
        fixture, market = row.get("fixture_id"), row.get("market")
        key = (fixture, market) if isinstance(market, str) else None
        if (not isinstance(fixture, str) or not fixture.strip()
                or not isinstance(market, str) or not market.strip()
                or key in seen):
            issues.append("record:%d:duplicate_or_missing" % i)
        else:
            seen.add(key)
        try:
            predicted = _timestamp(row["predicted_at"])
            kickoff = _timestamp(row["kickoff_at"])
            settled = _timestamp(row["settled_at"])
            if not predicted < kickoff < settled:
                raise ValueError("temporal leakage")
        except (KeyError, TypeError, ValueError, OverflowError):
            issues.append("record:%d:timestamp_invalid_or_leakage" % i)
            continue
        if settled < boundary:
            train.append(row)
        elif predicted >= boundary:
            test.append(row)
        else:
            issues.append("record:%d:boundary_overlap" % i)
    if len(train) < min_train:
        issues.append("train:insufficient")
    if len(test) < min_test:
        issues.append("test:insufficient")
    return {"status": "CHRONOLOGICAL_SPLIT_READY" if not issues else "BLOCKED",
            "issues": issues, "train": train if not issues else [],
            "test": test if not issues else [], "evaluation_start": evaluation_start,
            "ex_final_allowed": False}
