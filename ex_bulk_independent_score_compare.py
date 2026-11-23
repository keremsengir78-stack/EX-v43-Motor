"""Bulk compare review fixtures to separately supplied independent match results.

Input CSV must have: date,home,away,home_goals,away_goals,provider,source_url.
No fuzzy aliases, no self-attestation, and no EX FINAL promotion.
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path


def compare(source, independent_rows):
    lookup = {}
    conflicts = set()
    for row in independent_rows:
        key = (row.get("date"), row.get("home"), row.get("away"))
        try:
            score = [int(row["home_goals"]), int(row["away_goals"])]
        except (KeyError, TypeError, ValueError):
            continue
        if min(score) < 0 or not all(key) or not row.get("provider") or not row.get("source_url", "").startswith("https://"):
            continue
        if key in lookup:
            conflicts.add(key)
        else:
            lookup[key] = (score, row["provider"], row["source_url"])
    result = {"matched": [], "conflicted": [], "unresolved": [],
              "independent_score_verified": False, "ex_final_allowed": False}
    for record in source:
        key = (record["date"], record["home"], record["away"])
        candidate = lookup.get(key)
        if key in conflicts:
            result["conflicted"].append({"index": record["index"], "reason": "DUPLICATE_INDEPENDENT_SOURCE"})
        elif candidate is None:
            result["unresolved"].append(record["index"])
        elif candidate[1].strip().lower() == record.get("secondary_provider", "").strip().lower():
            result["unresolved"].append(record["index"])
        elif candidate[0] != record["matched_score"]:
            result["conflicted"].append({"index": record["index"], "reason": "SCORE_MISMATCH",
                                          "expected": record["matched_score"], "independent": candidate[0]})
        else:
            result["matched"].append({"index": record["index"], "score": candidate[0],
                                      "provider": candidate[1], "source_url": candidate[2],
                                      "review_status": "SOURCE_MATCH_PENDING_INDEPENDENCE_AUDIT"})
    result["counts"] = {k: len(result[k]) for k in ("matched", "conflicted", "unresolved")}
    return result


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python ex_bulk_independent_score_compare.py independent.csv output.json")
    with open(sys.argv[1], newline="", encoding="utf-8-sig") as f:
        independent = list(csv.DictReader(f))
    fixtures = []
    for n in range(1, 13):
        batch = json.loads((Path(__file__).resolve().parent / "reports" /
                            ("strict_score_review_batch_%02d.json" % n)).read_text(encoding="utf-8"))
        fixtures.extend(batch["fixtures"])
    if len(fixtures) != 1177 or sorted(r["index"] for r in fixtures) != list(range(1177)):
        raise SystemExit("Review batch scope invalid")
    result = compare(fixtures, independent)
    Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
