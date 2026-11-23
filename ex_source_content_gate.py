"""Fail-closed comparison of independently captured source-page content.

This gate verifies that supplied text snapshots contain exact fixture facts.
It cannot attest that a URL was fetched, that a publisher is official, or that
two providers are editorially independent. Those require separate audit.
"""
import hashlib
import json


FIELDS = ("fixture_id", "home_team", "away_team", "kickoff_at", "home_goals", "away_goals")


def compare_source_content(observations, expected):
    issues = []
    if not isinstance(expected, dict) or any(k not in expected for k in FIELDS):
        return {"status": "BLOCKED", "issues": ["expected:invalid"], "ex_final_allowed": False}
    if not isinstance(observations, list) or len(observations) < 2:
        return {"status": "BLOCKED", "issues": ["sources:insufficient"], "ex_final_allowed": False}
    providers = set()
    digests = set()
    for i, row in enumerate(observations):
        if not isinstance(row, dict):
            issues.append("source:%d:invalid" % i)
            continue
        group = row.get("provider_group")
        if not isinstance(group, str) or not group.strip() or group.strip().casefold() in providers:
            issues.append("source:%d:provider_duplicate_or_missing" % i)
        else:
            providers.add(group.strip().casefold())
        snapshot = row.get("captured_content")
        if not isinstance(snapshot, str) or not snapshot.strip():
            issues.append("source:%d:content_missing" % i)
            continue
        digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
        if row.get("content_sha256") != digest:
            issues.append("source:%d:content_digest_mismatch" % i)
        if digest in digests:
            issues.append("source:%d:identical_snapshot" % i)
        digests.add(digest)
        # Machine-readable facts must be embedded in the captured snapshot;
        # metadata alone cannot claim that the page contains a score.
        try:
            parsed = json.loads(snapshot)
        except (ValueError, TypeError):
            issues.append("source:%d:content_not_structured" % i)
            continue
        if not isinstance(parsed, dict) or any(
                type(parsed.get(k)) is not type(expected[k]) or parsed.get(k) != expected[k]
                for k in FIELDS):
            issues.append("source:%d:fixture_content_conflict" % i)
    return {"status": "CONTENT_CONSISTENT_UNATTESTED" if not issues else "BLOCKED",
            "issues": issues, "provider_groups": len(providers) if not issues else 0,
            "content_verified_by_live_fetch": False, "official_source_attested": False,
            "editorial_independence_attested": False, "ex_final_allowed": False}
