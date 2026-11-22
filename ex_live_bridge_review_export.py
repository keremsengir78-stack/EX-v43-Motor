"""Export unresolved fixtures from the provisional comparison for manual source review."""
import argparse
import csv
import json
from pathlib import Path


FIELDS = ("league", "date", "home", "away", "reason", "review_status")


def review_rows(report):
    if report.get("ex_final_allowed") is not False:
        raise ValueError("review report must keep EX FINAL blocked")
    queue = report.get("review_queue")
    if not isinstance(queue, list):
        raise ValueError("review queue missing")
    rows = []
    seen = set()
    for item in queue:
        if not isinstance(item, dict) or not isinstance(item.get("fixtures"), list):
            raise ValueError("invalid review queue")
        if len(item["fixtures"]) != item.get("unmatched"):
            raise ValueError("review queue count mismatch")
        for fixture in item["fixtures"]:
            if not isinstance(fixture, dict):
                raise ValueError("invalid fixture")
            row = {field: fixture.get(field) for field in FIELDS[:-1]}
            if any(not isinstance(value, str) or not value.strip() for value in row.values()):
                raise ValueError("missing fixture identity")
            if row["league"] != item.get("league") or row["date"] != item.get("day"):
                raise ValueError("fixture belongs to different review group")
            identity = tuple(row[field] for field in FIELDS[:-1])
            if identity in seen:
                raise ValueError("duplicate review fixture")
            seen.add(identity)
            row["review_status"] = "REQUIRES_INDEPENDENT_SOURCE_REVIEW"
            rows.append(row)
    if len(rows) != report.get("reviewed_unmatched"):
        raise ValueError("incomplete review queue")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--out", default="ex_live_bridge_review_queue.csv")
    args = parser.parse_args()
    report = json.loads(Path(args.audit).read_text())
    rows = review_rows(report)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"exported": len(rows), "ex_final_allowed": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
