"""Manual research settlement using the existing EX official archive verifier."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from math import sqrt
from pathlib import Path
from statistics import mean

from ex_decision import MARKETS
from ex_history_archive import utc
from ex_model_optimization import block_uncertainty, measure
from ex_performance_v1 import CANDIDATE, KEYS, REFERENCE
from run_ex_prospective_pipeline import archive_history


def wilson(successes, total):
    if not total:
        return None
    q = successes / total
    z = 1.959963984540054
    denom = 1 + z*z/total
    centre = (q + z*z/(2*total))/denom
    width = z * sqrt(q*(1-q)/total + z*z/(4*total*total)) / denom
    return [centre-width, centre+width]


def evaluate(examples, market):
    if not examples:
        return {"n": 0, "metrics": None}
    rows, predictions = zip(*examples, strict=True)
    values, _ = measure(rows, predictions, market)
    correct = sum((p >= .5) == r["labels"][market] for r, p in examples)
    high = [(r["labels"][market], p) for r, p in examples if p >= .70]
    hits = sum(y for y, _ in high)
    return {**values, "correct_at_50_pct": correct, "accuracy_wilson_95_descriptive": wilson(correct, len(rows)),
            "observed_positive_count": sum(r["labels"][market] for r in rows),
            "high_mean_probability": mean(p for _, p in high) if high else None,
            "high_hit_wilson_95_descriptive": wilson(hits, len(high)),
            "weekly_metric_intervals": block_uncertainty(rows, predictions, market)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--evidence-root", required=True, type=Path)
    p.add_argument("--audit-dir", required=True, type=Path)
    p.add_argument("--settlement-packs", required=True, type=Path)
    args = p.parse_args()
    root = args.evidence_root / "records/batch-analysis"
    audit = args.audit_dir

    def load_json(path):
        return json.loads(path.read_bytes())

    audit_seal = load_json(audit / "seal.json")
    for name, digest in audit_seal["file_sha256"].items():
        if hashlib.sha256((audit / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Invalid audited evidence digest: {name}")
    paths = [root / "2026-11-27/daily-close-1501-trt/decision.json",
             root / "2026-11-28/daily-research/decision.json",
             root / "2026-11-27_2026-11-29/discrimination-3072f15/29-kasim-karar.json"]
    decisions = {}
    for path in paths:
        seal = load_json(path.parent / "seal.json")
        if hashlib.sha256(path.read_bytes()).hexdigest() != seal["file_sha256"][path.name]:
            raise ValueError("Original decision digest mismatch")
        for row in load_json(path)["fixtures"]:
            event = row["fixture"]["event_id"]
            if event in decisions:
                raise ValueError("Duplicate original fixture")
            decisions[event] = row
    ledger = [json.loads(line) for line in (audit / "original-prematch.jsonl").read_text().splitlines()]
    elo = {r["event_id"]: r for line in (audit/'elo-ms2-tracking.jsonl').read_text().splitlines() for r in [json.loads(line)]}
    now = datetime.now(timezone.utc)
    verified, conflicts = {}, set()
    archive_history(args.settlement_packs, [], now, verified_outcomes=verified, conflicts=conflicts)
    models = ("DAILY_RESEARCH", REFERENCE, CANDIDATE, "STAT_FORM", "STAT_WORKLOAD", "STAT_VENUE5", "ELO_MS2")
    events = defaultdict(dict)
    for entry in ledger:
        event = entry["event_id"]
        if event not in verified or event in conflicts:
            continue
        _, actual, _ = verified[event]
        kick = utc(entry["kickoff"])
        if (not utc(entry["calculated_at"]) < utc(entry["sealed_at"]) < kick < utc(actual["finished"])
                or utc(actual["kickoff"]) != kick or actual["teams"] != entry["teams"] or actual["league"] != entry["league"]):
            raise ValueError(f"Settlement identity or time mismatch: {event}")
        truth = {"kickoff": kick, "labels": actual["labels"]}
        decision = decisions[event]
        probabilities = {**decision["probabilities"], "DAILY_RESEARCH": entry["original_research"]}
        for name in (REFERENCE, CANDIDATE):
            grid = (decision["reference_and_v1"] or {}).get(name)
            if grid:
                probabilities[name] = {m: grid[key] for m,key in KEYS.items()}
        track = elo.get(event)
        if track:
            if (track["teams"] != entry["teams"] or utc(track["kickoff"]) != kick
                    or utc(track["tracking_seal_at"]) >= kick):
                raise ValueError("Elo tracking does not match the fixture or pregame interval")
            probabilities["ELO_MS2"] = {"MS2": track["probability"]}
        for name, model in probabilities.items():
            for market, probability in model.items():
                events[market].setdefault(name, {})[event] = (truth, probability)
    output = {}
    for market in MARKETS:
        group = events[market]
        eligible = sorted(set.intersection(*(set(group.get(name, {}))
                          for name in ("DAILY_RESEARCH", REFERENCE, CANDIDATE))))
        output[market] = {"all_available_by_model": {name: evaluate(list(group.get(name, {}).values()), market)
                                                    for name in models if name != "ELO_MS2" or market == "MS2"},
                          "same_matches_reference_v1_daily": {
                              name: evaluate([group[name][event] for event in eligible], market)
                              for name in ("DAILY_RESEARCH", REFERENCE, CANDIDATE)}}
        if market == "MS2":
            ids = sorted(set(group.get("ELO_MS2", {})) & set(group.get(REFERENCE, {})))
            output[market]["same_matches_elo_reference"] = {
                name: evaluate([group[name][event] for event in ids], market) for name in ("ELO_MS2", REFERENCE)}
    print(json.dumps({"evaluated_at": now.isoformat(), "scope": "RESEARCH_PERFORMANCE_ONLY",
                      "matches_with_verified_results": len(set(verified) & set(decisions) - conflicts),
                      "markets": output}, indent=2))


if __name__ == "__main__":
    main()
