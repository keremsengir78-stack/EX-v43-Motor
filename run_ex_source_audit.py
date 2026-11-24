"""Classify score evidence per fixture without inferring upstream independence."""

import argparse
import json
from collections import Counter
from pathlib import Path

from ex_history_archive import atomic_write


def audit(ledger, dfl=None):
    records = {}

    def add(row, provider):
        key = tuple(row[k] for k in ("league", "date", "home", "away"))
        entry = records.setdefault(key, {"providers": set(), "scores": set(), "proof": set()})
        entry["scores"].add((row["home_goals"], row["away_goals"]))
        entry["providers"].add(provider)

    for name, queue in ledger["queues"].items():
        for row in queue["provisional_matches"]:
            add(row, "ESPN")
        for row in ledger.get("alternative_bundesliga", {}).get("queues", {}).get(name, {}).get("verified", []):
            add(row, "OpenLigaDB")

    for group in ledger.get("reviewed_score_matches", {}).values():
        for label, rows in group.items():
            for row in rows:
                key = tuple(row[k] for k in ("league", "date", "home", "away"))
                if key in records:
                    records[key]["scores"].add((row["home_goals"], row["away_goals"]))
                    records[key]["proof"].add(label)

    for item in (dfl or {}).get("fixtures", []):
        key = "de.1", item["date"], item["home"], item["away"]
        if key in records:
            row = records[key]
            row["scores"].add(tuple(item["official_score"]))
            row["proof"].add("dfl_official_result")

    categories = {}
    for key, item in sorted(records.items()):
        if len(item["scores"]) > 1:
            category = "CONFLICT"
        elif "independently_confirmed_result_matches" in item["proof"]:
            category = "REVIEWED_INDEPENDENT_RESULT_ONLY"
        elif item["proof"]:
            category = "OFFICIAL_RESULT_CORROBORATION_ONLY"
        else:
            category = "UPSTREAM_LINEAGE_UNPROVEN"
        categories.setdefault(category, []).append({
            **dict(zip(("league", "date", "home", "away"), key, strict=True)),
            "providers": sorted(item["providers"]), "proof": sorted(item["proof"]),
            "scores": sorted(item["scores"]), "upstream_lineage_certified": False,
        })
    return {"total": len(records), "counts": {k: len(v) for k, v in categories.items()},
            "categories": categories, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--dfl", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(json.loads(args.ledger.read_text()), json.loads(args.dfl.read_text()) if args.dfl else None)
    atomic_write(args.output, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"total": report["total"], "counts": report["counts"]}))


if __name__ == "__main__":
    main()
