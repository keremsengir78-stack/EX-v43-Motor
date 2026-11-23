"""Fail-closed evidence gate for strict score reconciliation reports.

A fixture match is not independent score verification. This module never
promotes EX FINAL; it only summarizes auditable evidence fields.
"""

from urllib.parse import urlsplit


def _valid_https_url(url):
    if not isinstance(url, str) or not url or any(ch.isspace() for ch in url):
        return False
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and bool(parsed.hostname) and
                not parsed.username and not parsed.password and not parsed.fragment and
                parsed.port in (None, 443))
    except (ValueError, TypeError):
        return False


def verify_strict_report(report):
    issues = []
    if not isinstance(report, dict):
        return {"status": "BLOCKED", "issues": ["report:invalid"],
                "independent_score_verified": False, "ex_final_allowed": False}
    total = report.get("total")
    confirmed = report.get("confirmed")
    remaining = report.get("remaining")
    if any(type(v) is not int or v < 0 for v in (total, confirmed, remaining)):
        issues.append("counts:invalid")
    elif confirmed + remaining != total:
        issues.append("counts:sum_mismatch")
    fixtures = report.get("verified")
    if not isinstance(fixtures, list):
        issues.append("fixtures:invalid")
        fixtures = []
    if type(confirmed) is int and len(fixtures) != confirmed:
        issues.append("fixtures:count_mismatch")
    seen_fixtures = set()
    for i, row in enumerate(fixtures):
        if not isinstance(row, dict) or not isinstance(row.get("fixture"), dict):
            issues.append("fixture:%d:invalid" % i)
            continue
        fixture = row["fixture"]
        # A repeated fixture must not inflate the independent confirmation count.
        identity = tuple(fixture.get(k) for k in ("fixture_id", "home_team", "away_team", "kickoff_at"))
        if all(isinstance(v, str) and v.strip() for v in identity):
            if identity in seen_fixtures:
                issues.append("fixture:%d:duplicate" % i)
            seen_fixtures.add(identity)
        if fixture.get("independent_score_verified") is not True:
            issues.append("fixture:%d:independent_source_unverified" % i)
        if row.get("verification") != "EXACT_TEAM_DATE_SCORE_MATCH":
            issues.append("fixture:%d:strict_match_missing" % i)
        if (not isinstance(row.get("secondary_provider"), str)
                or not row["secondary_provider"].strip()
                or not isinstance(row.get("secondary_url"), str)
                or not _valid_https_url(row["secondary_url"])):
            issues.append("fixture:%d:source_provenance_missing" % i)
    return {"status": "BLOCKED" if issues else "EVIDENCE_FIELDS_PRESENT_NOT_CERTIFIED",
            "issues": issues,
            "independent_score_verified": False,
            "ex_final_allowed": False}
