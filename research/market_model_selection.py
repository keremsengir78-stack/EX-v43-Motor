"""Manual, research-only comparison of sealed whole-match and market selections."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from ex_decision import MARKETS
from ex_history_archive import utc
from ex_model_optimization import measure
from ex_performance_v1 import CANDIDATE, KEYS, REFERENCE
from ex_research_scorelines import reconcile
from run_ex_prospective_pipeline import archive_history

STAT = ("STAT_FORM", "STAT_WORKLOAD", "STAT_VENUE5")


def validation_rank(stats, historical):
    aliases = {REFERENCE: "EX_REFERENCE", CANDIDATE: "V1"}
    result = {}
    for market in MARKETS:
        validation = {n: stats["models"][n]["markets"][market]["validation"]["brier"] for n in STAT}
        validation.update({n: historical["markets"][market]["models"][alias]["validation"]["brier"]
                           for n, alias in aliases.items()})
        if market == "MS2":
            validation["ELO_MS2"] = historical["markets"][market]["models"]["ELO"]["validation"]["brier"]
        result[market] = dict(sorted(validation.items(), key=lambda item: (item[1], item[0])))
    return result


def market_pick(models, ranking):
    values, selected = {}, {}
    for market, candidates in ranking.items():
        for name in candidates:
            if market in models.get(name, {}):
                values[market] = models[name][market]
                selected[market] = name
                break
    joint = reconcile(values) if len(values) == len(MARKETS) else {"status": "MISSING_MARKETS"}
    return {"models": selected, "probabilities": values, "scoreline": joint}


def checked(path, parents):
    manifest = json.loads((parents / "seal.json").read_bytes())
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    if manifest["file_sha256"][path.name] != digest:
        raise ValueError(f"Sealed input digest mismatch: {path.name}")
    return raw


def metrics_group(rows, key, market):
    if not rows:
        return {"n": 0, "metrics": None}
    return measure(rows, [row[key][market] for row in rows], market)[0]


def metric_report(rows):
    result = {}
    for market in MARKETS:
        paired = [r for r in rows if market in r["daily"] and market in r["per_market"]]
        coherent = [r for r in paired if r["status"] == "FEASIBLE"]
        names = (*STAT, REFERENCE, CANDIDATE, *(("ELO_MS2",) if market == "MS2" else ()))
        result[market] = {"paired_all": {k: metrics_group(paired,k,market) for k in ("daily","per_market")},
                          "paired_score_coherent": {k: metrics_group(coherent,k,market) for k in ("daily","per_market")},
                          "by_model": {name: metrics_group(
                            [{**r, "model": r["individual"][name]} for r in rows if market in r["individual"].get(name,{})],
                            "model",market) for name in names},
                          "same_matches_elo_vs_ex": None}
        if market == "MS2":
            elo = [r for r in rows if {"ELO_MS2", REFERENCE} <= r["individual"].keys()]
            result[market]["same_matches_elo_vs_ex"] = {
                name: metrics_group([{**r, "model": r["individual"][name]} for r in elo], "model", market)
                for name in ("ELO_MS2", REFERENCE)}
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive", type=Path, required=True)
    ap.add_argument("--fixture-status", type=Path, required=True)
    ap.add_argument("--settlements", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--frozen-policy", type=Path, help="Prospective report as sealed before kickoff")
    ap.add_argument("--frozen-policy-sha256")
    args = ap.parse_args()
    base = args.archive / "records/batch-analysis"
    window = base / "2026-11-27_2026-11-29"
    audit = window / "performance-cutoff-1531-trt"
    original = [json.loads(l) for l in checked(audit/"original-prematch.jsonl", audit).splitlines()]
    elo = {r["event_id"]: r for l in checked(audit/"elo-ms2-tracking.jsonl", audit).splitlines() for r in [json.loads(l)]}
    stack = window / "discrimination-3072f15"
    historical = json.loads(checked(stack/"comparison.json", stack))
    stats_path = window/"model-optimization-0c50aee/sonuclar.json"
    stats_raw = stats_path.read_bytes()
    paths = [base/"2026-11-27/daily-close-1501-trt/decision.json",base/"2026-11-28/daily-research/decision.json",stack/"29-kasim-karar.json"]
    closing = json.loads((paths[0].parent/"seal.json").read_bytes())
    if sha256(stats_raw).hexdigest() != closing["optimization_archive_sha256"]:
        raise ValueError("Frozen statistical validation digest mismatch")
    ranking = validation_rank(json.loads(stats_raw)["common_statistical_comparison"], historical)
    decisions = {}
    for path in paths:
        for r in json.loads(checked(path,path.parent))["fixtures"]:
            event = r["fixture"]["event_id"]
            if event in decisions:
                raise ValueError("Duplicate decision")
            decisions[event] = r
    status = json.loads(args.fixture_status.read_bytes())
    now = datetime.now(timezone.utc)
    prior_policy = {}
    if (args.frozen_policy is None) != (args.frozen_policy_sha256 is None):
        ap.error("--frozen-policy and --frozen-policy-sha256 are required together")
    if args.frozen_policy:
        raw = args.frozen_policy.read_bytes()
        if sha256(raw).hexdigest() != args.frozen_policy_sha256:
            raise ValueError("Frozen policy digest mismatch")
        prior = json.loads(raw)
        if prior["validation_order"] != ranking or utc(prior["computed_at"]) >= now:
            raise ValueError("Frozen policy differs from the validation protocol")
        prior_policy = {r["fixture"]["event_id"]: (utc(prior["computed_at"]), r) for r in prior["matches"]}
    verified, conflicts = {}, set()
    archive_history(args.settlements, [], now, verified_outcomes=verified, conflicts=conflicts)
    matches, scored = [], []
    for original_row in original:
        event=original_row["event_id"]
        row=decisions[event]
        fixture = row["fixture"]
        kickoff=utc(original_row["kickoff"])
        if not (utc(original_row["calculated_at"]) < utc(original_row["sealed_at"]) < kickoff):
            raise ValueError("Original forecast was not sealed pre-match")
        models = dict(row["probabilities"])
        pair = row.get("reference_and_v1") or {}
        if pair and pair["settings"] == historical["parameters"]["v1"]:
            for name in (REFERENCE, CANDIDATE):
                models[name] = {m: pair[name][key] for m,key in KEYS.items()}
        track = elo.get(event)
        if track and track["teams"] == fixture["team_ids"] and utc(track["kickoff"]) == kickoff and utc(track["tracking_seal_at"]) < kickoff:
            models["ELO_MS2"] = {"MS2": track["probability"]}
        per_market=market_pick(models,ranking)
        state = ("POSTPONED" if event in status["postponed"] else
                 "ACTIVE_PREMATCH" if status["fixtures"][event]["state"]=="pre" and now<kickoff else "INACTIVE")
        preview = {"fixture":fixture,"state":state,"original":original_row["original_research"],"individual":models,
                   "market_policy":per_market,"policy_frozen_before_kickoff":now < kickoff}
        if event in verified and event not in conflicts and state != "POSTPONED":
            _, actual, _ = verified[event]
            if (actual["teams"] != original_row["teams"] or actual["league"] != original_row["league"]
                    or utc(actual["kickoff"]) != kickoff or utc(actual["finished"]) <= kickoff):
                raise ValueError("Verified outcome identity mismatch")
            # A newly specified policy can only be measured from a pre-kickoff artifact.
            frozen_at, frozen_row = prior_policy.get(event, (now, {}))
            accepted = (frozen_at < kickoff and frozen_row.get("state") == "ACTIVE_PREMATCH"
                        and frozen_row.get("fixture") == fixture and frozen_row.get("market_policy") == per_market)
            scored.append({"kickoff":kickoff, "labels":actual["labels"], "individual":models,
                           "daily":preview["original"],"per_market":per_market["probabilities"] if accepted else {},
                           "status":per_market["scoreline"]["status"]})
        matches.append(preview)
    with args.output.open("x") as handle:
        json.dump({"computed_at":now.isoformat(),"scope":"RESEARCH_ONLY","validation_order":ranking,
       "counts":dict(Counter(x["state"] for x in matches)), "verified_results":len(scored), "metrics":metric_report(scored),
       "prospective_test_required":True, "matches":matches},handle,ensure_ascii=False,indent=2)
        handle.write("\n")


if __name__ == "__main__":
    main()
