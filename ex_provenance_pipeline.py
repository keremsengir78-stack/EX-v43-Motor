"""EX v4.3 provider reconciliation with provenance metadata enforcement.

This gate checks consistency, not external authenticity. Metadata validation
does not prove evidence URL content or reviewer independence.
"""
import datetime as dt
from ex_provenance_audit import validate_provenance
from ex_provider_reconciliation import reconcile_provider_fixtures
from ex_settlement_gate import verify_settlement_records


def reconcile_with_provenance(provider_inputs, attestations, cutoff, settlements=None):
    provenance = validate_provenance(attestations, cutoff)
    if provenance["status"] != "PROVENANCE_METADATA_READY_UNVERIFIED":
        return {"status": "BLOCKED", "issues": ["provenance:" + x for x in provenance["issues"]],
                "provenance": provenance, "reconciliation": None,
                "externally_verified": False, "ex_final_allowed": False}
    if not isinstance(provider_inputs, list) or not isinstance(attestations, list):
        return {"status": "BLOCKED", "issues": ["inputs:invalid"],
                "provenance": provenance, "reconciliation": None,
                "externally_verified": False, "ex_final_allowed": False}
    if (any(not isinstance(row, dict)
            or not isinstance(row.get("provider_group"), str)
            or not row["provider_group"].strip()
            for row in provider_inputs + attestations)):
        return {"status": "BLOCKED", "issues": ["inputs:provider_group_invalid"],
                "provenance": provenance, "reconciliation": None,
                "externally_verified": False, "ex_final_allowed": False}
    provider_groups = {row["provider_group"] for row in provider_inputs}
    attested_groups = {row["provider_group"] for row in attestations}
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
    if settlements is None:
        return {"status": "BLOCKED", "issues": ["settlement:missing"],
                "provenance": provenance, "reconciliation": reconciliation,
                "externally_verified": False, "ex_final_allowed": False}
    settlement = verify_settlement_records(settlements, agreed["fixture_id"],
                                            agreed["kickoff_at"], cutoff)
    if settlement["status"] != "SETTLEMENT_METADATA_READY_UNVERIFIED":
        return {"status": "BLOCKED",
                "issues": ["settlement:" + x for x in settlement["issues"]],
                "provenance": provenance, "reconciliation": reconciliation,
                "settlement": settlement, "externally_verified": False,
                "ex_final_allowed": False}
    if {row["provider_group"] for row in settlements} != provider_groups:
        return {"status": "BLOCKED", "issues": ["settlement:provider_group_mismatch"],
                "provenance": provenance, "reconciliation": reconciliation,
                "settlement": settlement, "externally_verified": False,
                "ex_final_allowed": False}
    try:
        normalized_source_by_group = {
            item["provider_group"]: item["source_id"] for item in provider_inputs
        }
        if any(row.get("source_id") != normalized_source_by_group[row["provider_group"]]
               for row in attestations):
            return {"status": "BLOCKED", "issues": ["provenance:source_id_mismatch"],
                    "provenance": provenance, "reconciliation": reconciliation,
                    "settlement": settlement, "externally_verified": False,
                    "ex_final_allowed": False}
        if any(row.get("source_id") != normalized_source_by_group[row["provider_group"]]
               for row in settlements):
            return {"status": "BLOCKED", "issues": ["settlement:source_id_mismatch"],
                    "provenance": provenance, "reconciliation": reconciliation,
                    "settlement": settlement, "externally_verified": False,
                    "ex_final_allowed": False}
        settlement_by_group = {
            row["provider_group"]: dt.datetime.fromisoformat(
                row["settled_at"].replace("Z", "+00:00"))
            for row in settlements
        }
        if any(dt.datetime.fromisoformat(
                row["reviewed_at"].replace("Z", "+00:00"))
                < settlement_by_group[row["provider_group"]]
                for row in attestations):
            return {"status": "BLOCKED",
                    "issues": ["provenance:review_before_settlement"],
                    "provenance": provenance, "reconciliation": reconciliation,
                    "settlement": settlement, "externally_verified": False,
                    "ex_final_allowed": False}
    except (KeyError, ValueError, TypeError, OverflowError):
        return {"status": "BLOCKED", "issues": ["provenance:settlement_review_invalid"],
                "provenance": provenance, "reconciliation": reconciliation,
                "settlement": settlement, "externally_verified": False,
                "ex_final_allowed": False}
    return {"status": "RECONCILED_WITH_METADATA_UNVERIFIED", "issues": [],
            "settlement": settlement,
            "provenance": provenance, "reconciliation": reconciliation,
            "externally_verified": False, "ex_final_allowed": False}
