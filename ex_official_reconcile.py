"""Reconcile official fixture observations with unresolved audit identities.

Official evidence is supplementary; it does not count as a second provider match.
"""
import argparse
import json
from pathlib import Path
from ex_official_evidence import validate_evidence


def reconcile_official_evidence(audit, document):
    validate_evidence(document)
    if audit.get("ex_final_allowed") is not False:
        raise ValueError("audit must remain provisional")
    if audit.get("as_of") != document["as_of"]:
        raise ValueError("cutoff mismatch")
    if audit.get("technical_gate") != "PASSED_AUDIT_COMPARISON":
        raise ValueError("untrusted audit baseline")
    if audit.get("review_queue_complete") is not True:
        raise ValueError("incomplete review queue")
    unresolved = []
    for group in audit["review_queue"]:
        unresolved.extend(group["fixtures"])
    if len(unresolved) != audit["reviewed_unmatched"]:
        raise ValueError("unresolved count mismatch")
    identities = {(f["league"], f["date"], f["home"], f["away"]) for f in unresolved}
    if len(identities) != len(unresolved):
        raise ValueError("duplicate unresolved identity")
    evidence = {(f["league"], f["date"], f["home"], f["away"]): f
                for f in document["records"]}
    if not set(evidence).issubset(identities):
        raise ValueError("evidence outside unresolved fixture queue")
    return {
        "status": "OFFICIAL_EVIDENCE_ATTACHED_NOT_PROVIDER_MERGED",
        "as_of": audit["as_of"],
        "reviewed_matched": audit["reviewed_matched"],
        "reviewed_unmatched": audit["reviewed_unmatched"],
        "official_evidence_attached": len(evidence),
        "official_evidence_missing": len(identities - set(evidence)),
        "official_evidence_records": [
            {**evidence[key], "provider_match_certified": False}
            for key in sorted(evidence)],
        "independent_sources_confirmed": False,
        "sample_sufficiency_certified": False,
        "calibration_certified": False,
        "ex_final_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--evidence", default="evidence/official_unresolved_2026_11.json")
    parser.add_argument("--out", default="ex_official_reconciliation_audit.json")
    args = parser.parse_args()
    result = reconcile_official_evidence(
        json.loads(Path(args.audit).read_text()),
        json.loads(Path(args.evidence).read_text()))
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: result[key] for key in (
        "status", "official_evidence_attached", "official_evidence_missing",
        "ex_final_allowed")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
