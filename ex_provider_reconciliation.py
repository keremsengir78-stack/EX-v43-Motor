"""EX v4.3 normalization-to-source-agreement bridge.

Normalization never confers verified status. An independent provenance reviewer
must explicitly attest each normalized record before cross-source comparison.
"""
from ex_provider_adapter import normalize_provider_fixture
from ex_source_agreement import verify_fixture_sources


def reconcile_provider_fixtures(provider_inputs, cutoff):
    issues = []
    observations = []
    if not isinstance(provider_inputs, list) or len(provider_inputs) < 2:
        return {"status": "BLOCKED", "issues": ["providers:insufficient"],
                "agreed_fixture": None, "ex_final_allowed": False}
    for i, item in enumerate(provider_inputs):
        if not isinstance(item, dict):
            issues.append("provider:%d:invalid" % i)
            continue
        normalized = normalize_provider_fixture(
            item.get("raw"), item.get("mapping"),
            item.get("source_id"), item.get("provider_group"))
        if normalized["status"] != "NORMALIZED_UNVERIFIED":
            issues.extend("provider:%d:%s" % (i, issue) for issue in normalized["issues"])
            continue
        # Verification must be an explicit upstream attestation; not inferred
        # from successful parsing, source names or matching fixture values.
        if item.get("independently_attested") is not True:
            issues.append("provider:%d:attestation_missing" % i)
            continue
        record = dict(normalized["record"])
        record["verified"] = True
        observations.append(record)
    if issues:
        return {"status": "BLOCKED", "issues": issues,
                "agreed_fixture": None, "ex_final_allowed": False}
    checked = verify_fixture_sources(observations, cutoff)
    return {"status": "RECONCILED_INPUT" if checked["status"] == "CROSS_VERIFIED_INPUT"
            else "BLOCKED",
            "issues": checked["issues"], "agreed_fixture": checked["agreed_fixture"],
            "independent_sources_confirmed": checked["independent_sources_confirmed"],
            "ex_final_allowed": False}
