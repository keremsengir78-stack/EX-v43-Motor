"""Extract review-only German team-name candidates from audited unresolved CSV.

No alias is approved or applied automatically. Candidate records are not verified scores.
"""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def candidates(rows):
    pairs = defaultdict(lambda: {"dates": set(), "seasons": set(), "fixtures": 0})
    for row in rows:
        if row.get("league") != "de.1":
            continue
        try:
            evidence = json.loads(row["source_evidence_json"])
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError("invalid German review evidence") from exc
        if evidence.get("source_presence_status") != "SECONDARY_SAME_DAY_SHARED_TEAM":
            continue
        primary_home, primary_away = row["home"], row["away"]
        for other in evidence.get("secondary_shared_team_candidates", []):
            if not isinstance(other, dict):
                raise ValueError("invalid secondary candidate")
            secondary_home, secondary_away = other.get("home"), other.get("away")
            if not isinstance(secondary_home, str) or not isinstance(secondary_away, str):
                raise ValueError("incomplete secondary candidate")
            # Exactly one side must already match literally. Never infer a
            # candidate from two simultaneously different team names.
            if primary_home == secondary_home and primary_away != secondary_away:
                primary, secondary = primary_away, secondary_away
            elif primary_away == secondary_away and primary_home != secondary_home:
                primary, secondary = primary_home, secondary_home
            else:
                continue
            key = (primary, secondary)
            pairs[key]["dates"].add(row["date"])
            pairs[key]["seasons"].add(row["season"])
            pairs[key]["fixtures"] += 1
    primary_to_secondary = defaultdict(set)
    secondary_to_primary = defaultdict(set)
    for p, s in pairs:
        primary_to_secondary[p].add(s)
        secondary_to_primary[s].add(p)
    return [
        {"league": "de.1", "primary_name": p, "secondary_name": s,
         "supporting_fixtures": v["fixtures"], "distinct_dates": len(v["dates"]),
         "seasons": sorted(v["seasons"]),
         "mapping_conflict": (len(primary_to_secondary[p]) > 1 or
                              len(secondary_to_primary[s]) > 1),
         "review_status": "MANUAL_REVIEW_REQUIRED",
         "auto_approved": False}
        for (p, s), v in sorted(pairs.items())
    ]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()
    with open(args.csv, newline="", encoding="utf-8") as f:
        result = candidates(csv.DictReader(f))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"candidates": result, "ex_final_allowed": False},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"German manual alias candidates: {len(result)}; EX FINAL BLOCKED")


if __name__ == "__main__":
    main()
