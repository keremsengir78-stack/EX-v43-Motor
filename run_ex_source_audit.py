"""Classify score evidence per fixture without inferring upstream independence."""

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from ex_history_archive import atomic_write
from ex_cross_verify import norm


def audit(ledger, dfl=None):
    records = {}
    seasons = defaultdict(set)

    def add(row, provider):
        key = tuple(row[k] for k in ("league", "date", "home", "away"))
        entry = records.setdefault(key, {"providers": set(), "scores": set(), "proof": set()})
        entry["scores"].add((row["home_goals"], row["away_goals"]))
        entry["providers"].add(provider)
        if row.get("season") is not None:
            seasons[key].add(str(row["season"]))

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

    normalized = defaultdict(list)
    for league, day, home, away in records:
        normalized[league, day, norm(home), norm(away)].append((league, day, home, away))
    source_candidates = defaultdict(set)
    for item in (dfl or {}).get("fixtures", []):
        league, day, home, away = item.get("league", "de.1"), item["date"], item["home"], item["away"]
        identity = league, day, norm(home), norm(away)
        source_candidates[identity].add((home, away))
    for item in (dfl or {}).get("fixtures", []):
        league, day, home, away = item.get("league", "de.1"), item["date"], item["home"], item["away"]
        key = league, day, home, away
        if key not in records:
            identity = league, day, norm(home), norm(away)
            candidates = normalized[identity]
            if (not identity[2] or not identity[3] or identity[2] == identity[3]
                    or len(candidates) != 1 or len(source_candidates[identity]) != 1):
                continue
            key = candidates[0]
        row = records[key]
        row["scores"].add(tuple(item["official_score"]))
        row["proof"].add(item.get("proof", "dfl_official_result"))

    categories = {}
    by_league_season = defaultdict(Counter)
    for key, item in sorted(records.items()):
        if len(item["scores"]) > 1:
            category = "CONFLICT"
        elif "independently_confirmed_result_matches" in item["proof"]:
            category = "REVIEWED_INDEPENDENT_RESULT_ONLY"
        elif item["proof"]:
            category = "OFFICIAL_RESULT_CORROBORATION_ONLY"
        else:
            category = "UPSTREAM_LINEAGE_UNPROVEN"
        season = next(iter(seasons[key])) if len(seasons[key]) == 1 else "unresolved"
        by_league_season[(key[0], season)][category] += 1
        categories.setdefault(category, []).append({
            **dict(zip(("league", "date", "home", "away"), key, strict=True)),
            "providers": sorted(item["providers"]), "proof": sorted(item["proof"]),
            "scores": sorted(item["scores"]), "upstream_lineage_certified": False,
        })
    return {"total": len(records), "counts": {k: len(v) for k, v in categories.items()},
            "categories": categories,
            "league_season_counts": [{"league": league, "season": season, "counts": dict(counts)}
                                     for (league, season), counts in sorted(by_league_season.items())],
            "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--dfl", type=Path)
    parser.add_argument("--official-results", type=Path, nargs="+", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    combined = json.loads(args.dfl.read_text()) if args.dfl else {"fixtures": []}
    for path in args.official_results:
        combined["fixtures"].extend(json.loads(path.read_text())["matches"])
    report = audit(json.loads(args.ledger.read_text()), combined)
    atomic_write(args.output, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"total": report["total"], "counts": report["counts"]}))


if __name__ == "__main__":
    main()
