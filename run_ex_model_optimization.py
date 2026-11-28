"""Evaluate and replay candidate models offline with separate research output."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter

from ex_component_workload_recovery import collect_completions, completion_tasks, recover_team_workload
from ex_decision import MARKETS
from ex_history_archive import HistoryArchive, utc
from ex_leagues import APPROVED_LEAGUES
from ex_model_optimization import BLENDS, REQUIRED, evaluate, historical_rows, score
from ex_pup_gate import execute_pup
from ex_research_components import archive_weather, weather_vector
from ex_retrospective import build_examples
from ex_rolling_scoreboards import archived_domestic_boards, scoreboard_facts
from run_ex_prospective_pipeline import archive_history, portable_facts


def read(path):
    return json.loads(path.read_bytes())


def daily_workload(row, review, observations, cutoff):
    fixture = row["fixture"]
    kickoff = utc(fixture["kickoff_at"])
    result = []
    workload_evidence = {}
    for side in ("home", "away"):
        team = fixture["team_ids"][side]
        context = row["observed_inputs"]["workload"].get(side, {})
        recovery = (review or {}).get("teams", {}).get(side, {})
        schedule = context.get("source_recent_schedule") or recovery.get("schedule")
        schedule_source = (row["observed_inputs"].get("summary_source") if context.get("source_recent_schedule")
                           else recovery.get("schedule_source"))
        if not schedule or not schedule_source or not schedule_source.get("retrieved_at"):
            workload_evidence[side] = {"team_id": team, "issue": "DATED_SCHEDULE_UNAVAILABLE"}
            continue
        if utc(schedule_source["retrieved_at"]) >= cutoff:
            workload_evidence[side] = {"team_id": team, "issue": "SCHEDULE_AFTER_CUTOFF"}
            continue
        known = dict(observations)
        for entry in context.get("completion_observations", []):
            known.setdefault(entry["event_id"], {
                "fact": {"event_id": entry["event_id"], "provider_completed": True, "terminal_status": "STATUS_FULL_TIME",
                         "teams": {side: team}, "kickoff": entry["kickoff_at"]},
                "source": {"sha256": entry["source_sha256"], "retrieved_at": entry["available_at"]},
            })
        # Always use the same start-to-start feature as training, even when
        # exact full-time markers also happen to be available.
        sample, issue = recover_team_workload(schedule, known, team, kickoff, cutoff, allow_kickoff_proxy=True)
        if sample is None:
            workload_evidence[side] = {"team_id": team, "issue": issue, "schedule_source": schedule_source}
            continue
        gap = (kickoff - utc(sample["matches"][-1]["fact"]["kickoff"])).total_seconds() / 3600
        result.extend((gap / 336, sample["completed_match_count"] / 5))
        workload_evidence[side] = {"kickoff_gap_hours": gap, "team_id": team,
                                   "completed_match_count": sample["completed_match_count"],
                                   "schedule_source": schedule_source,
                                   "completed_event_sources": [{"event_id": match["fact"].get("event_id"), **match["source"]}
                                                               for match in sample["matches"]]}
    return (tuple(result) if len(result) == 4 else None), workload_evidence


def replay(daily, reviews, observations, models, cutoff):
    rows = []
    for row, sealed in daily:
        start = perf_counter()
        fixture = row["fixture"]
        kickoff = utc(fixture["kickoff_at"])
        review = reviews.get(fixture["event_id"])
        source_cutoff = utc(row["as_of"])
        in_window = source_cutoff <= sealed <= cutoff < kickoff <= cutoff + timedelta(hours=96)
        strength = {m: row["component_research"][m]["components"]["team_strength"]["score"] for m in MARKETS}
        workload, workload_evidence = daily_workload(row, review, observations, cutoff) if in_window else (None, None)
        inputs = {"strength": strength if all(v is not None for v in strength.values()) else None,
                  "short": row.get("venue5_research") or None,
                  "kickoff_workload": workload,
                  "external": weather_vector(row["observed_inputs"].get("prematch_weather_forecast"),
                                             fixture["kickoff_at"], cutoff) if in_window else None}
        predictions = {}
        for name, model in models.items():
            if in_window and utc(model["trained_through"]) < cutoff:
                probabilities = {market: score(model, inputs, market) for market in MARKETS}
                if all(value is not None for value in probabilities.values()):
                    predictions[name] = probabilities
        baseline = (row.get("domestic_research") or {}).get("baseline")
        pup = execute_pup(row["markets"]["markets"], MARKETS, row["market_values"], baseline, requested=True) if predictions else None
        rows.append({"fixture": fixture, "cutoff": cutoff.isoformat(), "source_cutoff": source_cutoff.isoformat(), "source_sealed_at": sealed.isoformat(),
                     "status": "RESEARCH_ONLY" if predictions else "NO_CANDIDATE",
                     "within_96h_research_window": in_window, "inputs": inputs,
                     "kickoff_workload_evidence": workload_evidence,
                     "candidates": predictions,
                     "missing_by_model": {name: [key for key in keys if inputs[key] is None]
                                          for name, keys in REQUIRED.items()},
                     "score_scenarios_reference": pup["score_scenarios"] if pup else None, "pup": pup,
                     "archived_tur2": row.get("tur2"), "archived_auto_control": row.get("auto_control_by_market"),
                     "seconds": perf_counter() - start, "ex_g": None, "ex_final_allowed": False})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--daily", nargs="+", required=True, type=Path,
                        help="Restored daily-analysis.json paths under each sealed artifact’s forecasts directory")
    parser.add_argument("--weather-packs", type=Path)
    parser.add_argument("--settlement-packs", type=Path)
    parser.add_argument("--weekly-packs", nargs="*", type=Path, default=[])
    parser.add_argument("--domestic-pack", type=Path)
    parser.add_argument("--workload-review", required=True, type=Path)
    parser.add_argument("--workload-observations", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--uncertainty", action="store_true")
    parser.add_argument("--completion-cache", type=Path, help="Manually refresh recent-match completion evidence")
    args = parser.parse_args()
    cutoff = datetime.now(timezone.utc)
    start = perf_counter()
    sources = {provider: league for league, (_, provider, *_) in APPROVED_LEAGUES.items()}
    facts = portable_facts(args.facts)
    conflicts = set()
    independently_reviewed = {}
    if args.settlement_packs:
        facts, _ = archive_history(args.settlement_packs, facts, cutoff, conflicts=conflicts,
                                   verified_outcomes=independently_reviewed)
    by_event = {row["event_id"]: row for row in facts}
    supplemental = [row for pack in args.weekly_packs for row in scoreboard_facts(pack, cutoff, conflicts=conflicts)]
    if args.domestic_pack:
        supplemental += archived_domestic_boards(args.domestic_pack, cutoff, APPROVED_LEAGUES)
    for row in supplemental:
        event = row["event_id"]
        prior = by_event.get(event)
        if prior and (any(prior[key] != row[key] for key in ("kickoff", "competition", "teams"))
                      or (prior["score"] is not None and prior["score"] != row["score"])):
            conflicts.add(event)
        elif prior is None or prior["score"] is None:
            # A scoreboard-only result becomes usable at its archive seal.
            by_event[event] = {**row, "finished": max(row["finished"], row["captured_at"])}
    eligible = [row for row in by_event.values() if row["event_id"] not in conflicts
                and row.get("finished") and row["finished"] < cutoff
                and row["captured_at"] < cutoff]
    weather = archive_weather(args.weather_packs, cutoff) if args.weather_packs else {}
    leagues = {row["event_id"]: sources[row["competition"]] for row in eligible if row["competition"] in sources}
    rows, coverage = historical_rows([row for row in build_examples(eligible) if row["event_id"] in leagues],
                                     leagues, weather)
    complete = evaluate(rows, ("STAT_FORM", *BLENDS), uncertainty=args.uncertainty)
    reference = evaluate(rows, ("STAT_FORM", "STAT_WORKLOAD", "STAT_VENUE5"), rows, uncertainty=args.uncertainty)
    broad = {name: evaluate(rows, (name,), uncertainty=args.uncertainty) for name in ("STAT_FORM", "STAT_VENUE5")}
    models = {name: result["model"] for report in (*broad.values(), reference, complete)
              for name, result in report["models"].items()}
    daily_receipts = [path.parent.parent / "receipt.json" for path in args.daily]
    daily = [(row, utc(read(receipt)["created_at"]))
             for path, receipt in zip(args.daily, daily_receipts, strict=True)
             for row in read(path)]
    if len({row["fixture"]["event_id"] for row, _ in daily}) != len(daily):
        raise ValueError("Duplicate replay event")
    reviews = {row["fixture"]["event_id"]: row for row in read(args.workload_review)}
    observations = read(args.workload_observations)["events"]
    completion_issues = {}
    requests = 0
    if args.completion_cache:
        tasks = completion_tasks([row for row, _ in daily], observations, cutoff)
        store = HistoryArchive(args.completion_cache, len(tasks))
        completed, completion_issues = collect_completions(tasks, store)
        observations.update(completed)
        requests = store.requests
        cutoff = datetime.now(timezone.utc)
    output = replay(daily, reviews, observations, models, cutoff)
    counts = Counter(name for row in output for name in row["candidates"])
    inputs = [args.facts, args.workload_review, args.workload_observations, *args.daily, *daily_receipts]
    report = {"method": "EX_OPTIMIZATION_RESEARCH_V1", "cutoff": cutoff.isoformat(), "archive_facts": len(facts),
              "historical_examples": len(rows), "coverage": coverage,
              "historical_source_coverage": {"usable_settled_matches": len(eligible),
                  "excluded_source_conflicts": len(conflicts),
                  "official_score_cross_checks": len(set(independently_reviewed) - conflicts),
                  "cross_checks_are_not_producer_lineage_approval": True,
                  "by_competition": dict(Counter(row["competition"] for row in eligible))}, "complete_case_comparison": complete,
              "common_statistical_comparison": reference, "broad_single_model_evaluations": broad,
              "daily_candidates": dict(counts), "daily_fixtures": len(output),
              "daily_with_candidate": sum(bool(row["candidates"]) for row in output),
              "daily": output, "seconds": perf_counter() - start, "network_requests": requests, "completion_issues": completion_issues,
              "inputs_sha256": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs},
              "production_allowed": False}
    with args.output.open("x") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
