"""Chronologically replay rolling domestic UCL research from permanent archives."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean

from ex_daily_research import MARKET_KEYS, rolling_domestic
from ex_history_archive import atomic_write, utc
from ex_model_challengers import date_partitions
from ex_decision import MARKETS
from ex_ucl_baseline import cross_league_baseline
from run_ex_prospective_pipeline import portable_facts


def replay(facts, examples):
    by_team = defaultdict(list)
    references = {row["event_id"]: row for row in examples}
    coverage = Counter()
    compared = []
    for row in facts:
        if row["score"] is not None and row["finished"] is not None:
            for team in row["teams"].values():
                by_team[team].append(row)
    for row in facts:
        if row["competition"] != "uefa.champions" or row["score"] is None:
            continue
        coverage["settled_ucl_targets"] += 1
        kickoff = row["kickoff"]
        fixture = {"team_ids": row["teams"], "event_id": row["event_id"]}
        inputs = rolling_domestic(fixture, by_team, kickoff, retrospective=True)
        if inputs is None:
            coverage["missing_unambiguous_current_membership"] += 1
            continue
        candidate = cross_league_baseline(*inputs, cutoff_date=kickoff.date().isoformat()).get("baseline")
        if candidate is None:
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
    return {"source_facts": len(facts), "reference_examples": len(examples),
            "scope": "RETROSPECTIVE_DATE_AND_FINAL_STATUS_RECONSTRUCTION",
            "coverage": dict(coverage), "paired": len(compared), "metrics": metrics,
            "production_allowed": False, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    examples = [json.loads(line) for line in args.examples.read_text().splitlines()]
    result = replay(portable_facts(args.facts), examples)
    atomic_write(args.output, json.dumps(result, indent=2).encode())
    print(json.dumps(result))


if __name__ == "__main__":
    main()
