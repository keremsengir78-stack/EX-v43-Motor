"""Evaluate frozen research challengers and compare archived daily fixtures."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ex_discrimination_experiment import evaluate, features, predict, prepare
from ex_history_archive import utc
from ex_leagues import APPROVED_LEAGUES
from ex_performance_v1 import replay
from ex_research_scorelines import reconcile
from run_ex_historical_evidence import replay_archived_facts
from run_ex_prospective_pipeline import portable_facts


def compare_daily(facts, reports, dates, parameters, evaluated_at, model_available_at):
    batches = []
    for report, day in zip(reports, dates, strict=True):
        for item in report["fixtures"]:
            f = item["fixture"]
            if f["date"] != day:
                raise ValueError("Daily input contains a fixture from outside its designated day")
            cutoff = utc(item["input_cutoff"])
            kickoff = utc(f["kickoff_at"])
            if not model_available_at < cutoff < kickoff:
                raise ValueError("Training or validation unavailable at the original forecast time")
            target = {"event_id": f["event_id"], "competition": APPROVED_LEAGUES[f["league"]][1],
                      "teams": f["team_ids"], "kickoff": kickoff, "as_of": cutoff}
            batches.append((target, item))
    dated = [t for t, _ in batches]
    if len({t["event_id"] for t in dated}) != len(dated):
        raise ValueError("Duplicate daily event")
    new = dict(features(facts, dated, archived=True))
    known = [{**f, "finished": max(f["finished"], f["captured_at"])}
             for f in facts if f["finished"] and f["captured_at"]]
    refs = {row["event_id"]: forms for row, forms in replay(known, dated)}
    results = []
    for target, item in batches:
        event = target["event_id"]
        adds, grids = {}, {}
        if event in new:
            inputs = item["inputs"]
            adds, grids = predict({**new[event], **inputs, "form": refs.get(event)}, parameters)
        results.append({"fixture": item["fixture"], "input_cutoff": item["input_cutoff"],
                        "original_research": item["probabilities"], "original_model": item["validation_choice"],
                        "original_reference_and_v1": item.get("reference_and_v1"),
                        "new_research": adds, "predicted_score_models": grids,
                        "score_compatibility": {k: reconcile(p) for k,p in adds.items()},
                        "computed_at": evaluated_at.isoformat(), "historical_research_replay": True,
                        "original_pup": item["research_pup"], "original_tur2": item["archived_tur2"],
                        "original_auto_control": item["archived_auto_control"], "ex_g": None, "ex_final_allowed": False})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-inputs", required=True, type=Path)
    parser.add_argument("--facts", required=True, type=Path)
    parser.add_argument("--daily", nargs=3, required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    primary = portable_facts(args.facts)
    facts = replay_archived_facts(args.archive_inputs, primary, now)
    facts = [r for r in facts if r["captured_at"] < now and (r["finished"] is None or r["finished"] < now)]
    dated = [json.loads(path.read_bytes()) for path in args.daily]
    earliest = min(utc(row["input_cutoff"]) for report in dated for row in report["fixtures"])
    rows, coverage = prepare([r for r in facts if r["kickoff"] < earliest and r["captured_at"] < earliest
                              and (r["finished"] is None or r["finished"] < earliest)])
    report = evaluate(rows)
    model_available_at = utc(report["validation_through"])
    daily = compare_daily(facts, dated, ("2026-11-27", "2026-11-28", "2026-11-29"),
                          report["parameters"], now, model_available_at)
    report.update(coverage=coverage, daily=daily, computed_at=now.isoformat(),
                  daily_model_coverage=dict(Counter(name for row in daily for name in row["new_research"])),
                  input_sha256={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in args.daily})
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
