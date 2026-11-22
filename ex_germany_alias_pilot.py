"""Generate a quarantined candidate-only alias map for a shadow reconciliation run.

This file MUST NOT be used as reviewed/approved evidence for EX FINAL.
"""
import argparse
import json
from pathlib import Path


def build_pilot(data):
    if data.get("ex_final_allowed") is not False:
        raise ValueError("candidate report must explicitly block EX FINAL")
    rows = data.get("candidates")
    if not isinstance(rows, list):
        raise ValueError("candidate list missing")
    primary_to_secondary = {}
    secondary_to_primary = {}
    for row in rows:
        if (row.get("league") != "de.1"
                or row.get("review_status") != "MANUAL_REVIEW_REQUIRED"
                or row.get("auto_approved") is not False
                or row.get("mapping_conflict") is not False):
            raise ValueError("unreviewed or conflicting candidate")
        p, s = row.get("primary_name"), row.get("secondary_name")
        if not isinstance(p, str) or not p.strip() or not isinstance(s, str) or not s.strip():
            raise ValueError("empty alias name")
        if p in primary_to_secondary and primary_to_secondary[p] != s:
            raise ValueError("primary maps to multiple secondary names")
        if s in secondary_to_primary and secondary_to_primary[s] != p:
            raise ValueError("secondary maps to multiple primary names")
        primary_to_secondary[p] = s
        secondary_to_primary[s] = p
    # Canonicalize secondary provider names to primary names for a test only.
    return {"de.1": dict(sorted(secondary_to_primary.items()))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--candidates", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    data = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    result = build_pilot(data)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"SHADOW PILOT ONLY: {len(result['de.1'])} candidates, not approved for EX FINAL")


if __name__ == "__main__":
    main()
