"""Export German unresolved secondary results without auto-reconciliation."""
import argparse
import csv
import json
from pathlib import Path

from ex_secondary_review_summary import summarize

FIELDS = ("season", "league", "date", "home", "away", "home_goals",
          "away_goals", "reason", "review_status", "source_evidence_json")


def germany_rows(audit):
    report = summarize(audit)
    rows = []
    for group in report["groups"]:
        if group["league"] != "de.1":
            continue
        for fixture in group["unmatched_details"]:
            if not isinstance(fixture, dict):
                raise ValueError("invalid unresolved fixture evidence")
            row = {field: fixture.get(field, "") for field in FIELDS}
            row["season"] = group["season"]
            row["league"] = group["league"]
            row["review_status"] = "REQUIRES_INDEPENDENT_SOURCE_REVIEW"
            row["source_evidence_json"] = json.dumps(fixture, ensure_ascii=False, sort_keys=True)
            rows.append(row)
    if len(rows) != report["germany_unmatched"]:
        raise ValueError("German unresolved count mismatch")
    rows.sort(key=lambda row: (str(row["season"]), str(row["date"]),
                               str(row["home"]), str(row["away"])))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    audit = json.loads(Path(args.audit).read_text(encoding="utf-8"))
    rows = germany_rows(audit)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"germany_unmatched": len(rows), "ex_final_allowed": False}))


if __name__ == "__main__":
    main()
