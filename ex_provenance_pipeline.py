"""EX v4.3 provider reconciliation with provenance metadata enforcement.

This gate checks consistency, not external authenticity. Metadata validation
does not prove evidence URL content or reviewer independence.
"""
import datetime as dt
from ex_provenance_audit import validate_provenance
from ex_provider_reconciliation import reconcile_provider_fixtures


def reconcile_with_provenance(provider_inputs, attestations, cutoff):
    provenance = validate_provenance(attestations, cutoff)
    if provenance["status"] != "PROVENANCE_METADATA_READY_UNVERIFIED":
        return {"status": "BLOCKED", "issues": ["provenance:" + x for x in provenance["issues"]],
                "provenance": provenance, "reconciliation": None,
                "externally_verified": False, "ex_final_allowed": False}
    if not isinstance(provider_inputs, list) or not isinstance(attestations, list):
        return {"status": "BLOCKED", "issues": ["inputs:invalid"],
                "provenance": provenance, "reconciliation": None,
                "externally_verified": False, "ex_final_allowed": False}
    provider_groups = {row.get("provider_group") for row in provider_inputs if isinstance(row, dict)}
    attested_groups = {row.get("provider_group") for row in attestations if isinstance(row, dict)}
    if len(provider_groups) != len(provider_inputs) or provider_groups != attested_groups:
        return {"status": "BLOCKED", "issues": ["provenance:provider_group_mismatch"],
                "provenance": provenance, "reconciliation": None,
                "externally_verified": False, "ex_final_allowed": False}
    reconciliation = reconcile_provider_fixtures(provider_inputs, cutoff)
    if reconciliation["status"] != "RECONCILED_INPUT":
        return {"status": "BLOCKED", "issues": ["reconciliation:" + x for x in reconciliation["issues"]],
                "provenance": provenance, "reconciliation": reconciliation,
                "externally_verified": False, "ex_final_allowed": False}
    agreed = reconciliation["agreed_fixture"]
    if any(row.get("fixture_id") != agreed["fixture_id"] for row in attestations):
        return {"status": "BLOCKED", "issues": ["provenance:fixture_mismatch"],
                "provenance": provenance, "reconciliation": reconciliation,
                "externally_verified": False, "ex_final_allowed": False}
    try:
        kickoff = dt.datetime.fromisoformat(agreed["kickoff_at"].replace("Z", "+00:00"))
        if any(dt.datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00")) <= kickoff
               for row in attestations):
            return {"status": "BLOCKED", "issues": ["provenance:review_before_or_at_kickoff"],
                    "provenance": provenance, "reconciliation": reconciliation,
                    "externally_verified": False, "ex_final_allowed": False}
    except (ValueError, TypeError, KeyError, OverflowError):
        return {"status": "BLOCKED", "issues": ["provenance:timestamp_invalid"],
                "provenance": provenance, "reconciliation": reconciliation,
                "externally_verified": False, "ex_final_allowed": False}
    return {"status": "RECONCILED_WITH_METADATA_UNVERIFIED", "issues": [],
            "provenance": provenance, "reconciliation": reconciliation,
            "externally_verified": False, "ex_final_allowed": False}
