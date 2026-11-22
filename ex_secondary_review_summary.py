"""Produce a lossless, deterministic manual-review report from ingestion audit evidence."""
import argparse
import json
from pathlib import Path


def summarize(audit):
    if not isinstance(audit, dict):
        raise ValueError("audit must be an object")
    queue = audit.get("secondary_review_queue")
    if not isinstance(queue, list):
        raise ValueError("secondary_review_queue missing")
    groups = []
    total = 0
    for group in queue:
        if not isinstance(group, dict) or not isinstance(group.get("unmatched"), list):
            raise ValueError("invalid secondary review group")
        season, league = group.get("season"), group.get("league")
        if not all(isinstance(x, str) and x.strip() for x in (season, league)):
            raise ValueError("missing group identity")
        unmatched = group["unmatched"]
        total += len(unmatched)
        groups.append({"season": season, "league": league,
                       "unmatched_count": len(unmatched),
                       "unmatched_details": unmatched})
    expected = audit.get("secondary_unverified")
    if type(expected) is not int or expected < 0 or expected != total:
        raise ValueError("unmatched totals disagree with audit")
    groups.sort(key=lambda g: (g["league"], g["season"]))
    return {"as_of": audit.get("as_of"), "unmatched_total": total,
            "groups": groups, "ex_final_allowed": False,
            "review_status": "REQUIRES_INDEPENDENT_SOURCE_REVIEW"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = summarize(json.loads(Path(args.audit).read_text(encoding="utf-8")))
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
                      encoding="utf-8")
    print(json.dumps({"unmatched_total": report["unmatched_total"],
                      "by_league": [{"league": g["league"], "season": g["season"],
                                     "unmatched": g["unmatched_count"]}
                                    for g in report["groups"]],
                      "ex_final_allowed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
