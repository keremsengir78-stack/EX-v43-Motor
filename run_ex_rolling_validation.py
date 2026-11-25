"""Chronologically replay rolling domestic UCL research from permanent archives."""

import argparse
import datetime as dt
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean

from ex_daily_research import DOMESTIC_BY_SLUG, MARKET_KEYS, domestic_snapshot, rolling_domestic
from ex_history_archive import atomic_write, utc
from ex_cross_verify import norm
from ex_history_sources import ESPN
from run_ucl_baselines import verified_bytes
from ex_model_challengers import date_partitions
from ex_decision import MARKETS
from ex_espn_provider import ESPN_LEAGUES
from ex_ucl_baseline import cross_league_baseline
from run_ex_prospective_pipeline import portable_facts


# These four club archives were reviewed for UCL research in prior packages.
# They remain outside the daily competition catalog.
CURATED_UCL_ARCHIVES = {ESPN_LEAGUES[league]: league for league in ("az.1", "cz.1", "sk.1", "ua.1")}


def supplemental_history(root, facts):
    """Map named archive rows to stable IDs through hash-verified UCL match cards."""
    rows, _, names, leagues, _ = domestic_snapshot(root)
    mapping = defaultdict(set)
    inverse = defaultdict(set)
    sources = json.loads((root / "fixture_verification.json").read_text())["sources"]
    for source in sources:
        if not source["url"].startswith(f"{ESPN}/uefa.champions/scoreboard?dates="):
            continue
        filename = Path(source["file"])
        if filename.name != str(filename):
            raise ValueError("Invalid UCL fixture evidence filename")
        board = json.loads(verified_bytes(root / filename, source["sha256"]))
        if {r["slug"] for r in board["leagues"]} != {"uefa.champions"}:
            raise ValueError("Unexpected UCL identity board")
        for event in board["events"]:
            match, = event["competitions"]
            for side in match["competitors"]:
                club = side["team"]
                canonical = names.get(norm(club["displayName"]))
                if canonical:
                    mapping[canonical].add(club["id"])
                    inverse[club["id"]].add(canonical)
    ids = {name: next(iter(values)) for name, values in mapping.items()
           if len(values) == 1 and len(inverse[next(iter(values))]) == 1}
    slugs = {league: slug for slug, league in (DOMESTIC_BY_SLUG | CURATED_UCL_ARCHIVES).items()}
    known = set()
    for fact in facts:
        if fact["score"] is not None and fact["competition"] in slugs.values():
            for side, club in fact["teams"].items():
                known.add((fact["competition"], fact["kickoff"].date(), side, club))
    # A date-only score becomes eligible only on a strictly later date.
    out = []
    for row in rows:
        slug = slugs.get(row["league"])
        sides = {side: ids.get(row[side]) if leagues.get(row[side]) == row["league"] else None
                 for side in ("home", "away")}
        if not slug or not any(sides.values()) or any(
                (slug, row["date"], side, club) in known for side, club in sides.items() if club):
            continue
        day = dt.datetime.combine(row["date"], dt.time.min, dt.timezone.utc)
        out.append({"competition": slug, "kickoff": day, "finished": day + dt.timedelta(days=1),
                    "teams": {side: club or "archive:" + row[side] for side, club in sides.items()},
                    "score": (row["hg"], row["ag"]), "evidence_scope": "DATE_ONLY_DOMESTIC_RECONSTRUCTION"})
    return out


def replay(facts, examples, supplemental=()):
    by_team = defaultdict(list)
    references = {row["event_id"]: row for row in examples}
    coverage = Counter()
    compared, fixture_audit = [], []
    for row in [*facts, *supplemental]:
        if row["score"] is not None and row["finished"] is not None:
            for team in row["teams"].values():
                by_team[team].append(row)
    for row in facts:
        if row["competition"] != "uefa.champions" or row["score"] is None:
            continue
        coverage["settled_ucl_targets"] += 1
        kickoff = row["kickoff"]
        fixture = {"team_ids": row["teams"], "event_id": row["event_id"]}
        diagnostic = {**fixture, "kickoff": kickoff.isoformat(), "status": "DOMESTIC_WINDOW_AVAILABLE"}
        fixture_audit.append(diagnostic)
        inputs = rolling_domestic(fixture, by_team, kickoff, retrospective=True,
                                  archive_leagues=CURATED_UCL_ARCHIVES if supplemental else None)
        if inputs is None:
            diagnostic["status"] = "MISSING_UNAMBIGUOUS_CURRENT_MEMBERSHIP"
            coverage["missing_unambiguous_current_membership"] += 1
            continue
        calculation = cross_league_baseline(*inputs, cutoff_date=kickoff.date().isoformat())
        diagnostic["domestic_leagues"] = calculation["domestic_leagues"]
        diagnostic["sample_counts"] = {side: sample["counts"] for side, sample in calculation["samples"].items()}
        candidate = calculation.get("baseline")
        if candidate is None:
            diagnostic["status"] = "INCOMPLETE_DOMESTIC_WINDOWS"
            coverage["incomplete_domestic_windows"] += 1
            continue
        ref = references.get(row["event_id"])
        coverage["rolling_baseline_available"] += 1
        if ref is None or utc(ref["kickoff"]) != kickoff:
            continue
        compared.append((kickoff.date(), ref, candidate))
    splits = date_partitions(compared)
    metrics = {}
    if splits:
        for scope, cohort in zip(("early", "validation", "test"), splits, strict=True):
            metrics[scope] = {"n": len(cohort), "markets": {
                market: {
                    "venue5_brier": mean((ref["short"][market] - ref["labels"][market]) ** 2
                                         for _, ref, _ in cohort),
                    "rolling_brier": mean((candidate[MARKET_KEYS[market]] - ref["labels"][market]) ** 2
                                          for _, ref, candidate in cohort),
                } for market in MARKETS}}
    return {"source_facts": len(facts), "reference_examples": len(examples), "supplemental_matches": len(supplemental),
            "scope": "RETROSPECTIVE_DATE_AND_FINAL_STATUS_RECONSTRUCTION",
            "coverage": dict(coverage), "fixture_audit": fixture_audit, "paired": len(compared), "metrics": metrics,
            "production_allowed": False, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--domestic", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    examples = [json.loads(line) for line in args.examples.read_text().splitlines()]
    facts = portable_facts(args.facts)
    result = replay(facts, examples, supplemental_history(args.domestic, facts) if args.domestic else ())
    atomic_write(args.output, json.dumps(result, indent=2).encode())
    print(json.dumps({key: value for key, value in result.items() if key != "fixture_audit"}))


if __name__ == "__main__":
    main()
