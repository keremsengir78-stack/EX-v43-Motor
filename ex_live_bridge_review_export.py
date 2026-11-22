"""Export unresolved fixtures from the provisional comparison for manual source review."""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path


FIELDS = ("league", "date", "home", "away", "reason", "review_status", "as_of", "source_reference")


def review_rows(report):
    if report.get("ex_final_allowed") is not False:
        raise ValueError("review report must keep EX FINAL blocked")
    as_of = report.get("as_of")
    if not isinstance(as_of, str):
        raise ValueError("audit cutoff missing")
    try:
        cutoff = dt.date.fromisoformat(as_of)
    except ValueError as exc:
        raise ValueError("invalid audit cutoff") from exc
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
            row = {field: fixture.get(field) for field in ("league", "date", "home", "away", "reason")}
            if any(not isinstance(value, str) or not value.strip() for value in row.values()):
                raise ValueError("missing fixture identity")
            try:
                fixture_day = dt.date.fromisoformat(row["date"])
            except ValueError as exc:
                raise ValueError("invalid fixture date") from exc
            if fixture_day > cutoff:
                raise ValueError("future fixture relative to audit cutoff")
            if row["league"] != item.get("league") or row["date"] != item.get("day"):
                raise ValueError("fixture belongs to different review group")
            identity = tuple(row[field] for field in ("league", "date", "home", "away", "reason"))
            if identity in seen:
                raise ValueError("duplicate review fixture")
            seen.add(identity)
            row["review_status"] = "REQUIRES_INDEPENDENT_SOURCE_REVIEW"
            row["as_of"] = as_of
            row["source_reference"] = "NOT_VERIFIED"
            rows.append(row)
    if len(rows) != report.get("reviewed_unmatched"):
        raise ValueError("incomplete review queue")
    rows.sort(key=lambda row: (row["league"], row["date"], row["home"], row["away"]))
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
