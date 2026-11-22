"""EX v4.3 provider provenance metadata gate.

Structural provenance checks only. URLs and reviewer IDs are not proof that a
source was visited or independently verified. No network requests occur here.
"""
import datetime as dt
from urllib.parse import urlparse


def validate_provenance(attestations, cutoff):
    issues = []
    try:
        if not isinstance(cutoff, str) or not cutoff.endswith("Z"):
            raise ValueError("UTC cutoff required")
        boundary = dt.datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        if boundary.utcoffset() != dt.timedelta(0):
            raise ValueError("UTC timezone required")
    except (ValueError, TypeError, OverflowError):
        boundary = None
        issues.append("cutoff:invalid")
    if not isinstance(attestations, list) or len(attestations) < 2:
        attestations = attestations if isinstance(attestations, list) else []
        issues.append("attestations:insufficient")
    seen_groups = set()
    seen_evidence = set()
    seen_urls = set()
    seen_reviewers = set()
    for i, row in enumerate(attestations):
        if not isinstance(row, dict):
            issues.append("attestation:%d:invalid" % i)
            continue
        group = row.get("provider_group")
        if not isinstance(group, str) or not group.strip() or group in seen_groups:
            issues.append("attestation:%d:group_duplicate_or_missing" % i)
        else:
            seen_groups.add(group)
        evidence_id = row.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id.strip() or evidence_id in seen_evidence:
            issues.append("attestation:%d:evidence_duplicate_or_missing" % i)
        else:
            seen_evidence.add(evidence_id)
        for field in ("reviewer_id", "fixture_id"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                issues.append("attestation:%d:%s_missing" % (i, field))
        reviewer = row.get("reviewer_id")
        if isinstance(reviewer, str) and reviewer.strip():
            if reviewer in seen_reviewers:
                issues.append("attestation:%d:reviewer_duplicate" % i)
            seen_reviewers.add(reviewer)
        url = row.get("evidence_url")
        if not isinstance(url, str) or not url.strip():
            issues.append("attestation:%d:url_invalid" % i)
        else:
            try:
                parsed = urlparse(url)
                if (url != url.strip() or parsed.scheme != "https"
                        or not parsed.hostname or parsed.username or parsed.password
                        or parsed.fragment or any(ch.isspace() for ch in url)):
                    issues.append("attestation:%d:url_invalid" % i)
                else:
                    normalized_url = (parsed.scheme.lower(), parsed.hostname.lower(),
                                      parsed.port or 443, parsed.path.rstrip("/") or "/",
                                      parsed.query)
                    if normalized_url in seen_urls:
                        issues.append("attestation:%d:url_duplicate" % i)
                    seen_urls.add(normalized_url)
            except ValueError:
                issues.append("attestation:%d:url_invalid" % i)
        try:
            stamp = row["reviewed_at"]
            if not isinstance(stamp, str) or not stamp.endswith("Z"):
                raise ValueError("UTC review required")
            when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if when.utcoffset() != dt.timedelta(0) or (boundary is not None and when >= boundary):
                raise ValueError("future review")
        except (KeyError, ValueError, TypeError, OverflowError):
            issues.append("attestation:%d:date_invalid_or_future" % i)
    fixture_ids = {row.get("fixture_id") for row in attestations
                   if isinstance(row, dict) and isinstance(row.get("fixture_id"), str)}
    if len(fixture_ids) > 1:
        issues.append("attestations:fixture_conflict")
    return {"status": "PROVENANCE_METADATA_READY_UNVERIFIED" if not issues else "BLOCKED",
            "issues": issues, "source_groups": len(seen_groups) if not issues else 0,
            "externally_verified": False, "ex_final_allowed": False}
