"""Fail-closed temporal checks for captured match evidence.

A valid timestamp does not attest publisher identity, official status, or live retrieval.
"""
from datetime import datetime, timezone, timedelta
import re

_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


def _parse_utc(value):
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise ValueError("noncanonical UTC timestamp")
    result = datetime.fromisoformat(value[:-1] + "+00:00")
    if result.utcoffset() != timedelta(0):
        raise ValueError("not UTC")
    return result


def audit_source_times(*, kickoff_at, published_at, captured_at, checked_at,
                       maximum_capture_age_seconds=86400):
    """Return BLOCKED unless timestamps are consistent and evidence is fresh.

    A result of TIME_CONSISTENT_UNATTESTED is never sufficient for EX FINAL.
    """
    issues = []
    if (type(maximum_capture_age_seconds) is not int
            or maximum_capture_age_seconds < 0):
        issues.append("invalid_maximum_age")
    try:
        kickoff = _parse_utc(kickoff_at)
        published = _parse_utc(published_at)
        captured = _parse_utc(captured_at)
        checked = _parse_utc(checked_at)
    except (ValueError, OverflowError, TypeError):
        issues.append("invalid_timestamp")
    else:
        if published < kickoff:
            issues.append("published_before_kickoff")
        if captured < published:
            issues.append("captured_before_publication")
        if checked < captured:
            issues.append("checked_before_capture")
        if not issues and (checked - captured).total_seconds() > maximum_capture_age_seconds:
            issues.append("stale_capture")
    return {"status": "BLOCKED" if issues else "TIME_CONSISTENT_UNATTESTED",
            "issues": issues, "live_fetch_attested": False,
            "official_source_attested": False, "ex_final_allowed": False}
