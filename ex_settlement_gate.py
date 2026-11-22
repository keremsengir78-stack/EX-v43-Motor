"""EX v4.3 finished-result gate with explicit settlement timestamps.

The gate validates structured provider assertions; it cannot independently
confirm that the match truly finished or that the evidence is authentic.
"""
import datetime as dt


def verify_settlement_records(records, fixture_id, kickoff_at, cutoff):
    issues = []
    try:
        def utc(value):
            if not isinstance(value, str) or not value.endswith("Z"):
                raise ValueError("UTC required")
            result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if result.utcoffset() != dt.timedelta(0):
                raise ValueError("UTC timezone required")
            return result
        kickoff = utc(kickoff_at)
        boundary = utc(cutoff)
        if kickoff >= boundary:
            issues.append("fixture:future")
    except (ValueError, TypeError, OverflowError):
        return {"status": "BLOCKED", "issues": ["time:invalid"], "settled_at": None,
                "externally_verified": False, "ex_final_allowed": False}
    if not isinstance(fixture_id, str) or not fixture_id.strip():
        return {"status": "BLOCKED", "issues": ["fixture:invalid"],
                "settled_at": None, "externally_verified": False,
                "ex_final_allowed": False}
    if not isinstance(records, list) or len(records) < 2:
        return {"status": "BLOCKED", "issues": ["settlements:insufficient"],
                "settled_at": None, "externally_verified": False, "ex_final_allowed": False}
    groups = set()
    times = []
    for i, row in enumerate(records):
        if not isinstance(row, dict):
            issues.append("settlement:%d:invalid" % i)
            continue
        group = row.get("provider_group")
        if not isinstance(group, str) or not group.strip() or group in groups:
            issues.append("settlement:%d:provider_duplicate_or_missing" % i)
        else:
            groups.add(group)
        if row.get("fixture_id") != fixture_id:
            issues.append("settlement:%d:fixture_mismatch" % i)
        if row.get("status") != "finished":
            issues.append("settlement:%d:not_finished" % i)
        try:
            settled = utc(row.get("settled_at"))
            if not kickoff < settled < boundary:
                raise ValueError("settlement outside valid interval")
            times.append(settled)
        except (ValueError, TypeError, OverflowError):
            issues.append("settlement:%d:time_invalid" % i)
    return {"status": "SETTLEMENT_METADATA_READY_UNVERIFIED" if not issues else "BLOCKED",
            "issues": issues, "settled_at": max(times).isoformat().replace("+00:00", "Z")
            if not issues else None, "externally_verified": False, "ex_final_allowed": False}
