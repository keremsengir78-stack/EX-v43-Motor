"""Produce a lossless, deterministic manual-review report from ingestion audit evidence."""
import argparse
import json
from pathlib import Path


def summarize(audit):
    if not isinstance(audit, dict):
        raise ValueError("audit must be an object")
    if audit.get("ex_final_allowed") is not False:
        raise ValueError("audit must explicitly block EX FINAL")
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
        suggestions = group.get("suggestions", [])
        if not isinstance(suggestions, list):
            raise ValueError("invalid alias suggestions")
        unmatched = group["unmatched"]
        total += len(unmatched)
        groups.append({"season": season, "league": league,
                       "unmatched_count": len(unmatched),
                       "unmatched_details": unmatched,
                       "alias_suggestions": suggestions})
    expected = audit.get("secondary_unverified")
    if type(expected) is not int or expected < 0 or expected != total:
        raise ValueError("unmatched totals disagree with audit")
    expected_by_season = audit.get("secondary_unmatched_by_season")
    if expected_by_season is not None:
        if not isinstance(expected_by_season, dict):
            raise ValueError("invalid season-level source counts")
        observed_by_season = {}
        for group in groups:
            key = group["season"] + "/" + group["league"]
            if key in observed_by_season:
                raise ValueError("duplicate season and league review group")
            observed_by_season[key] = group["unmatched_count"]
        expected_positive = {key: value for key, value in expected_by_season.items()
                             if type(value) is int and value > 0}
        if (any(type(value) is not int or value < 0
                for value in expected_by_season.values())
                or observed_by_season != expected_positive):
            raise ValueError("season-level source counts disagree with review queue")
    groups.sort(key=lambda g: (g["league"], g["season"]))
    by_league = {}
    for group in groups:
        league = group["league"]
        by_league[league] = by_league.get(league, 0) + group["unmatched_count"]
    source_errors = audit.get("secondary_source_errors", [])
    if not isinstance(source_errors, list):
        raise ValueError("invalid independent source errors")
    return {"as_of": audit.get("as_of"), "unmatched_total": total,
            "unmatched_by_league": dict(sorted(by_league.items())),
            "germany_unmatched": by_league.get("de.1", 0),
            "groups": groups, "source_errors": source_errors,
            "groups_with_alias_suggestions": sum(bool(g["alias_suggestions"]) for g in groups),
            "ex_final_allowed": False,
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
                      "unmatched_by_league": report["unmatched_by_league"],
                      "germany_unmatched": report["germany_unmatched"],
                      "by_league": [{"league": g["league"], "season": g["season"],
                                     "unmatched": g["unmatched_count"]}
                                    for g in report["groups"]],
                      "ex_final_allowed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
