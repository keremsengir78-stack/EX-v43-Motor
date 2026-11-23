"""Fail-closed comparison of independently captured source-page content.

This gate verifies that supplied text snapshots contain exact fixture facts.
It cannot attest that a URL was fetched, that a publisher is official, or that
two providers are editorially independent. Those require separate audit.
"""
import hashlib
import json
import datetime as dt
import re
import unicodedata


def _identity(value):
    """Canonical comparison key; never evidence of publisher independence."""
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


FIELDS = ("fixture_id", "home_team", "away_team", "kickoff_at", "home_goals", "away_goals")


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_nonfinite(value):
    raise ValueError("non-finite JSON number")


def compare_source_content(observations, expected):
    issues = []
    if not isinstance(expected, dict) or any(k not in expected for k in FIELDS):
        return {"status": "BLOCKED", "issues": ["expected:invalid"], "ex_final_allowed": False}
    # A matching snapshot must never legitimize impossible fixture metadata.
    fixture_id = expected.get("fixture_id")
    home = expected.get("home_team")
    away = expected.get("away_team")
    kickoff = expected.get("kickoff_at")
    goals = (expected.get("home_goals"), expected.get("away_goals"))
    if (not isinstance(fixture_id, str) or not fixture_id.strip()
            or not isinstance(home, str) or not home.strip()
            or not isinstance(away, str) or not away.strip()
            or _identity(home) == _identity(away)
            or any(type(g) is not int or g < 0 or g > 30 for g in goals)):
        return {"status": "BLOCKED", "issues": ["expected:invalid_fixture_facts"],
                "ex_final_allowed": False}
    try:
        if not isinstance(kickoff, str) or not re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", kickoff):
            raise ValueError("noncanonical kickoff")
        dt.datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
    except (ValueError, OverflowError, TypeError):
        return {"status": "BLOCKED", "issues": ["expected:invalid_kickoff"],
                "ex_final_allowed": False}
    if not isinstance(observations, list) or len(observations) < 2:
        return {"status": "BLOCKED", "issues": ["sources:insufficient"], "ex_final_allowed": False}
    providers = set()
    digests = set()
    for i, row in enumerate(observations):
        if not isinstance(row, dict):
            issues.append("source:%d:invalid" % i)
            continue
        group = row.get("provider_group")
        if not isinstance(group, str) or not group.strip() or _identity(group) in providers:
            issues.append("source:%d:provider_duplicate_or_missing" % i)
        else:
            providers.add(_identity(group))
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
            parsed = json.loads(snapshot, object_pairs_hook=_reject_duplicate_keys,
                                parse_constant=_reject_nonfinite)
        except (ValueError, TypeError):
            issues.append("source:%d:content_not_structured" % i)
            continue
        if not isinstance(parsed, dict) or any(
                type(parsed.get(k)) is not type(expected[k]) or parsed.get(k) != expected[k]
                for k in FIELDS):
            issues.append("source:%d:fixture_content_conflict" % i)
        # A caller-controlled provider_group must not contradict an explicit
        # publisher identity embedded in the supplied snapshot. This is still
        # not proof that either publisher actually served the content.
        if isinstance(parsed, dict) and "publisher" in parsed:
            publisher = parsed["publisher"]
            if (not isinstance(publisher, str) or not publisher.strip()
                    or not isinstance(group, str)
                    or _identity(publisher) != _identity(group)):
                issues.append("source:%d:publisher_identity_conflict" % i)
    return {"status": "CONTENT_CONSISTENT_UNATTESTED" if not issues else "BLOCKED",
            "issues": issues, "provider_groups": len(providers) if not issues else 0,
            "content_verified_by_live_fetch": False, "official_source_attested": False,
            "editorial_independence_attested": False, "ex_final_allowed": False}
