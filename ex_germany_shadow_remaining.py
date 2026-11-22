"""Export exact unmatched shadow fixtures for manual investigation, never approve them."""
import argparse
import csv
import json
from pathlib import Path


def extract(audit):
    groups = audit.get("secondary_review_queue")
    counts = audit.get("secondary_unmatched_by_season")
    if not isinstance(groups, list) or not isinstance(counts, dict):
        raise ValueError("shadow audit lacks unmatched evidence")
    rows = []
    for group in groups:
        if group.get("league") != "de.1":
            continue
        season = group.get("season")
        for item in group.get("unmatched", []):
            if not isinstance(item, dict):
                raise ValueError("invalid unmatched item")
            rows.append({"season": season, "league": "de.1", **item})
    expected = sum(v for k, v in counts.items() if k.endswith("/de.1"))
    if len(rows) != expected or expected != audit.get("secondary_unverified"):
        raise ValueError("shadow unmatched detail count differs from audit")
    return {"unmatched_total": expected, "fixtures": rows,
            "comparison_only": True, "aliases_approved": False,
            "ex_final_allowed": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--audit", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    report = extract(json.loads(Path(a.audit).read_text(encoding="utf-8")))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+chr(10),
                   encoding="utf-8")
    print(f"Unverified shadow fixtures: {report['unmatched_total']}")


if __name__ == "__main__":
    main()
