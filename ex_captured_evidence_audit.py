"""Combined fail-closed audit of supplied source snapshots and their chronology.

This is an offline evidence consistency check, NOT proof of live retrieval,
official publication, editorial independence or EX FINAL readiness.
"""
from ex_source_content_gate import compare_source_content
from ex_source_time_gate import audit_source_times


def audit_captured_fixture_evidence(observations, expected, checked_at,
                                    maximum_capture_age_seconds=86400):
    """Audit fixture facts and each source's chronology without attesting origin."""
    content = compare_source_content(observations, expected)
    issues = ["content:" + issue for issue in content["issues"]]
    time_results = []
    if isinstance(observations, list):
        for index, row in enumerate(observations):
            if not isinstance(row, dict):
                issues.append("source:%d:time_metadata_missing" % index)
                continue
            result = audit_source_times(
                kickoff_at=expected.get("kickoff_at") if isinstance(expected, dict) else None,
                published_at=row.get("published_at"),
                captured_at=row.get("captured_at"),
                checked_at=checked_at,
                maximum_capture_age_seconds=maximum_capture_age_seconds,
            )
            time_results.append(result)
            issues.extend("source:%d:time:%s" % (index, issue)
                          for issue in result["issues"])
    else:
        issues.append("sources:invalid")
    return {
        "status": "BLOCKED" if issues else "CONSISTENT_UNATTESTED",
        "issues": issues,
        "content_audit": content,
        "time_audits": time_results,
        "live_fetch_attested": False,
        "official_source_attested": False,
        "editorial_independence_attested": False,
        "calibrated_probability": None,
        "ex_final_allowed": False,
    }
