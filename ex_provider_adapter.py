"""Strict provider-record normalization for EX v4.3.

Explicit field mappings only; no guessing, scraping, implicit trust, or
automatic promotion of normalized records to verified evidence.
"""
import datetime as dt


def normalize_provider_fixture(raw, mapping, source_id, provider_group):
    issues = []
    if not isinstance(raw, dict) or not isinstance(mapping, dict):
        return {"status": "BLOCKED", "issues": ["input:invalid"], "record": None,
                "ex_final_allowed": False}
    for label, value in (("source_id", source_id), ("provider_group", provider_group)):
        if not isinstance(value, str) or not value.strip():
            issues.append(label + ":missing")
    required = ("fixture_id", "home_team", "away_team", "kickoff_at",
                "home_goals", "away_goals")
    normalized = {}
    for key in required:
        mapped = mapping.get(key)
        if not isinstance(mapped, str) or not mapped.strip() or mapped not in raw:
            issues.append(key + ":mapping_missing")
        else:
            normalized[key] = raw[mapped]
    if issues:
        return {"status": "BLOCKED", "issues": issues, "record": None,
                "ex_final_allowed": False}
    for key in ("fixture_id", "home_team", "away_team"):
        if not isinstance(normalized[key], str) or not normalized[key].strip():
            issues.append(key + ":invalid")
    for key in ("home_goals", "away_goals"):
        value = normalized[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            issues.append(key + ":invalid")
    try:
        stamp = normalized["kickoff_at"]
        if not isinstance(stamp, str) or not stamp.endswith("Z"):
            raise ValueError("UTC required")
        when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if when.utcoffset() != dt.timedelta(0):
            raise ValueError("timezone missing")
    except (TypeError, ValueError, OverflowError):
        issues.append("kickoff_at:invalid")
    if issues:
        return {"status": "BLOCKED", "issues": issues, "record": None,
                "ex_final_allowed": False}
    normalized.update({"source_id": source_id, "provider_group": provider_group,
                       "verified": False})
    return {"status": "NORMALIZED_UNVERIFIED", "issues": [],
            "record": normalized, "ex_final_allowed": False}
