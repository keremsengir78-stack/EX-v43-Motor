"""Offline, evidence-only Germany alias candidate coverage analysis.

Never upgrades source evidence or approves EX FINAL.
"""
import argparse
import csv
import json
from pathlib import Path
from ex_germany_alias_pilot import build_pilot


def analyze(rows, candidate_data):
    mapping = build_pilot(candidate_data)["de.1"]
    # Reverse mapping is only used to compare the displayed names.
    reverse = {primary: secondary for secondary, primary in mapping.items()}
    total = 0
    unique = 0
    ambiguous = 0
    for row in rows:
        if row.get("league") != "de.1":
            continue
        total += 1
        evidence = json.loads(row["source_evidence_json"])
        matches = [
            other for other in evidence.get("secondary_shared_team_candidates", [])
            if ((other.get("home") == row["home"] and
                 other.get("away") == reverse.get(row["away"]))
                or (other.get("away") == row["away"] and
                    other.get("home") == reverse.get(row["home"])))
        ]
        if len(matches) == 1:
            unique += 1
        elif len(matches) > 1:
            ambiguous += 1
    return {"germany_unmatched_baseline": total,
            "unique_name_only_candidates": unique,
            "ambiguous_name_candidates": ambiguous,
            "still_unverified": total,
            "verified_score_matches_added": 0,
            "aliases_approved": False, "ex_final_allowed": False,
            "method": "same-day shared opponent and candidate alias; no score verification",
            "comparison_only": True}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--candidates", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    with open(a.csv, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    data = json.loads(Path(a.candidates).read_text(encoding="utf-8"))
    result = analyze(rows, data)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
