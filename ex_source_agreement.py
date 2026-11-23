"""EX v4.3 independent-source agreement gate for fixture result records.

Sources must be explicitly supplied, distinct and independently verified.
This is a structural agreement check, not proof of true editorial independence.
"""
import datetime as dt
from urllib.parse import urlsplit

FIELDS = ("fixture_id", "home_team", "away_team", "kickoff_at", "home_goals", "away_goals")


def verify_fixture_sources(observations, cutoff, require_evidence_locator=False):
    issues = []
    try:
        if not isinstance(cutoff, str) or not cutoff.endswith("Z"):
            raise ValueError("UTC cutoff")
        boundary = dt.datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        if boundary.utcoffset() != dt.timedelta(0):
            raise ValueError("timezone required")
    except (ValueError, TypeError, OverflowError):
        issues.append("cutoff:invalid")
        boundary = None
    if not isinstance(observations, list) or len(observations) < 2:
        observations = observations if isinstance(observations, list) else []
        issues.append("sources:insufficient")
    source_ids = set()
    provider_groups = set()
    evidence_urls = set()
    values = []
    for i, row in enumerate(observations):
        if not isinstance(row, dict):
            issues.append("source:%d:invalid" % i)
            continue
        sid = row.get("source_id")
        if not isinstance(sid, str) or not sid.strip() or sid in source_ids:
            issues.append("source:%d:duplicate_or_missing" % i)
        else:
            source_ids.add(sid)
        group = row.get("provider_group")
        if not isinstance(group, str) or not group.strip() or group in provider_groups:
            issues.append("source:%d:provider_group_duplicate_or_missing" % i)
        else:
            provider_groups.add(group)
        if row.get("verified") is not True:
            issues.append("source:%d:unverified" % i)
        if require_evidence_locator:
            url = row.get("evidence_url")
            try:
                parsed = urlsplit(url)
                if (parsed.scheme != "https" or not parsed.hostname or
                        parsed.username or parsed.password or any(ch.isspace() for ch in url)):
                    raise ValueError("invalid evidence locator")
                normalized_url = parsed._replace(fragment="").geturl()
                if normalized_url in evidence_urls:
                    issues.append("source:%d:duplicate_evidence_url" % i)
                evidence_urls.add(normalized_url)
            except (ValueError, TypeError, AttributeError):
                issues.append("source:%d:evidence_url_missing_or_invalid" % i)
            try:
                stamp = row.get("retrieved_at")
                if not isinstance(stamp, str) or not stamp.endswith("Z"):
                    raise ValueError("retrieval must be UTC")
                retrieved = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
                if retrieved.utcoffset() != dt.timedelta(0) or (boundary is not None and retrieved > boundary):
                    raise ValueError("retrieval after cutoff")
                event = row.get("kickoff_at")
                if isinstance(event, str) and event.endswith("Z"):
                    kickoff_time = dt.datetime.fromisoformat(event.replace("Z", "+00:00"))
                    if retrieved < kickoff_time:
                        raise ValueError("retrieval before fixture")
            except (ValueError, TypeError, AttributeError, OverflowError):
                issues.append("source:%d:retrieved_at_missing_or_invalid" % i)
        if any(field not in row for field in FIELDS):
            issues.append("source:%d:fields_missing" % i)
            continue
        if any(not isinstance(row[k], str) or not row[k].strip()
               for k in ("fixture_id", "home_team", "away_team")):
            issues.append("source:%d:identity_invalid" % i)
        if any(isinstance(row[k], bool) or not isinstance(row[k], int) or row[k] < 0 or row[k] > 30
               for k in ("home_goals", "away_goals")):
            issues.append("source:%d:score_invalid" % i)
        try:
            stamp = row["kickoff_at"]
            if not isinstance(stamp, str) or not stamp.endswith("Z"):
                raise ValueError("UTC kickoff")
            kickoff = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if kickoff.utcoffset() != dt.timedelta(0) or (boundary is not None and kickoff >= boundary):
                raise ValueError("future kickoff")
        except (ValueError, TypeError, OverflowError, AttributeError):
            issues.append("source:%d:kickoff_invalid_or_future" % i)
        # Preserve untrusted values for equality checks without trusting their types.
        values.append(tuple(row.get(k) for k in FIELDS))
    if len(values) >= 2 and any(value != values[0] for value in values[1:]):
        issues.append("sources:fixture_conflict")
    return {"status": "CROSS_VERIFIED_INPUT" if not issues else "BLOCKED",
            "issues": issues, "independent_sources_confirmed": len(provider_groups) if not issues else 0,
            "agreed_fixture": dict(zip(FIELDS, values[0])) if values and not issues else None,
            "ex_final_allowed": False}
