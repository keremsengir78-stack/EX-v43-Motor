"""Bulk compare review fixtures to separately supplied independent match results.

Input CSV must have: date,home,away,home_goals,away_goals,provider,source_url.
No fuzzy aliases, no self-attestation, and no EX FINAL promotion.
"""
import csv
import datetime as dt
from urllib.parse import urlsplit
import json
import sys
from collections import Counter
from pathlib import Path


def compare(source, independent_rows):
    lookup = {}
    conflicts = set()
    for row in independent_rows:
        if not isinstance(row, dict):
            continue
        key = (row.get("date"), row.get("home"), row.get("away"))
        try:
            raw_scores = (row["home_goals"], row["away_goals"])
            if any(type(v) not in (str, int) or not str(v).isdigit() for v in raw_scores):
                continue
            score = [int(v) for v in raw_scores]
        except (KeyError, TypeError, ValueError):
            continue
        try:
            date = dt.date.fromisoformat(key[0])
            if date.isoformat() != key[0] or any(not isinstance(v, str) or not v.strip() for v in key):
                continue
            url = row.get("source_url")
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.fragment or parsed.port not in (None, 443)
                    or any(ch.isspace() for ch in url)):
                continue
        except (TypeError, ValueError, AttributeError):
            continue
        if min(score) < 0 or max(score) > 30 or not isinstance(row.get("provider"), str) or not row["provider"].strip():
            continue
        if key in lookup:
            conflicts.add(key)
        else:
            lookup[key] = (score, row["provider"], row["source_url"])
    result = {"matched": [], "conflicted": [], "unresolved": [],
              "independent_score_verified": False, "ex_final_allowed": False}
    for record in source:
        if not isinstance(record, dict):
            result["unresolved"].append(None)
            continue
        index = record.get("index")
        key = (record.get("date"), record.get("home"), record.get("away"))
        if (any(not isinstance(v, str) or not v.strip() for v in key)
                or not isinstance(record.get("matched_score"), list)
                or len(record["matched_score"]) != 2
                or any(type(v) is not int or v < 0 or v > 30 for v in record["matched_score"])):
            result["unresolved"].append(index)
            continue
        candidate = lookup.get(key)
        if key in conflicts:
            result["conflicted"].append({"index": index, "reason": "DUPLICATE_INDEPENDENT_SOURCE"})
        elif candidate is None:
            result["unresolved"].append(record["index"])
        elif candidate[1].strip().lower() == str(record.get("secondary_provider") or "").strip().lower():
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
