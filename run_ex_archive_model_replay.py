"""Independently verify the archived research cohort without creating forecasts."""

import argparse
from collections import Counter, defaultdict
import datetime as dt
import json
import math
from pathlib import Path

from ex_daily_research import rolling_domestic
from ex_decision import MARKETS, WEIGHTS
from ex_evidence_store import restore
from ex_history_archive import atomic_write, utc
from ex_performance_v1 import CANDIDATE, KEYS, REFERENCE, attach_daily, settled_daily_pairs
from ex_pup_gate import execute_pup
from ex_ucl_baseline import cross_league_baseline
from run_ex_historical_evidence import replay_archived_facts
from run_ex_prospective_pipeline import (archive_history, combine_forecasts, portable_facts,
                                         read_forecast_pack, select_evaluation_rows)
from run_ex_prospective_validation import evaluate, join_holdout


def verify_score_grid(model, dependence=0.):
    """Cross-check market marginals and score scenarios with an independent PMF recurrence."""
    def pmf(rate):
        values = [math.exp(-rate)]
        for goals in range(1, 48):
            values.append(values[-1] * rate / goals)
        return values

    home, away = pmf(model["lambda_home"]), pmf(model["lambda_away"])
    home_rate, away_rate = model["lambda_home"], model["lambda_away"]
    rho = max(-min(1 / home_rate, 1 / away_rate), min(dependence, 1, 1 / (home_rate * away_rate))) if dependence else 0.
    grid = [(h, a, hp * ap) for h, hp in enumerate(home) for a, ap in enumerate(away)]
    # Move equal probability mass between the four low-score cells.
    shift = home[1] * away[1] * rho
    grid = [(h, a, p + (shift if h != a else -shift) if h <= 1 and a <= 1 else p)
            for h, a, p in grid]
    cells = {(h, a): p for h, a, p in grid}
    checks = {
        "over25": lambda h, a: h + a >= 3,
        "btts": lambda h, a: h > 0 and a > 0,
        "home_win": lambda h, a: h > a,
        "away_win": lambda h, a: a > h,
        "draw": lambda h, a: h == a,
        "probability_mass": lambda h, a: True,
    }
    maximum_error = max(abs(math.fsum(p for h, a, p in grid if check(h, a)) - model[key])
                        for key, check in checks.items())
    return {"max_abs_error": maximum_error, "scenarios": {
        "1-1": cells[1, 1], "2-0": cells[2, 0], "3-0": cells[3, 0],
        "one_sided_three_plus": math.fsum(p for h, a, p in grid if (h >= 3 and a == 0) or (a >= 3 and h == 0)),
    }}


def form_samples_agree(replayed, archived):
    for side in ("home", "away"):
        new, old = replayed[side], archived[side]
        if {k: v for k, v in new.items() if k != "result"} != {k: v for k, v in old.items() if k != "result"}:
            return False
        if any(abs(a - b) > 1e-12 for a, b in zip(new["result"], old["result"], strict=True)):
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("store", "work", "output"):
        parser.add_argument(f"--{field}", type=Path, required=True)
    parser.add_argument("--artifact", action="append", required=True)
    args = parser.parse_args()
    for kind, files in {
        "historical-facts": None, "frozen-candidates": None, "weekly-capacity": None, "ucl-domestic-research": None,
        "settlement-and-performance": None, "prematch-and-research": {"forecasts/daily-analysis.json", "forecasts/forecasts.jsonl"},
    }.items():
        restore(args.store, kind, args.work / kind, files=files)
    facts_path = next((args.work / "historical-facts").glob("*/historical-facts.jsonl"))
    original_facts = portable_facts(facts_path)
    primary_seal = utc(json.loads((facts_path.parent / "receipt.json").read_bytes())["created_at"])
    cohort, results = set(), []
    for artifact in args.artifact:
        pack = args.work / "prematch-and-research" / artifact
        sealed = utc(json.loads((pack / "receipt.json").read_bytes())["created_at"])
        rows = json.loads((pack / "forecasts/daily-analysis.json").read_bytes())
        selected = [row for row in rows if (row.get("domestic_research") or {}).get("baseline")]
        grouped = defaultdict(list)
        for row in selected:
            grouped[utc(row["as_of"])].append(row)
        for cutoff, archived in grouped.items():
            if primary_seal >= cutoff:
                raise ValueError("Primary historical receipt was unavailable at forecast time")
            facts = replay_archived_facts(args.work, original_facts, cutoff)
            book = defaultdict(list)
            for fact in facts:
                for club in fact["teams"].values():
                    book[club].append(fact)
            staged, observations = [], {}
            for row in archived:
                fixture = row["fixture"]
                event = fixture["event_id"]
                if event in cohort or not cutoff <= sealed < utc(fixture["kickoff_at"]):
                    raise ValueError("Duplicated event or seal outside its pre-match interval")
                cohort.add(event)
                diagnostics = {}
                inputs = rolling_domestic(fixture, book, cutoff, diagnostics=diagnostics)
                baseline = cross_league_baseline(*inputs, cutoff_date=cutoff.date().isoformat()) if inputs else {}
                staged.append({"fixture": fixture, "domestic_research": baseline})
                observations[event] = diagnostics
            settings = archived[0]["performance_v1"]["settings"]
            if any(row["performance_v1"]["settings"] != settings for row in archived):
                raise ValueError("Unmatched candidate model settings")
            attach_daily(staged, facts, cutoff, {"settings": settings})
            for before, after in zip(archived, staged, strict=True):
                fixture = before["fixture"]
                event = fixture["event_id"]
                baseline = after["domestic_research"].get("baseline")
                got = after.get("performance_v1", {})
                if not baseline or not got:
                    results.append({"fixture": fixture, "issues": ["ARCHIVED_FORM_OR_V1_NOT_REPLAYED"],
                                    "form_diagnostics": observations[event]})
                    continue
                old = before["performance_v1"]
                differences = {version: max(abs(got[version][key] - old[version][key]) for key in KEYS.values())
                               for version in (REFERENCE, CANDIDATE)}
                form_matches = form_samples_agree(
                    json.loads(json.dumps(after["domestic_research"]["samples"])), before["domestic_research"]["samples"])
                grid = {REFERENCE: verify_score_grid(baseline), CANDIDATE: verify_score_grid(got[CANDIDATE], settings[2])}
                issues = [key for key, condition in {
                    "FORM_MISMATCH": not form_matches,
                    "REPLAY_PROBABILITY_MISMATCH": max(differences.values()) > 1e-12,
                    "SCORE_GRID_MISMATCH": any(check["max_abs_error"] > 1e-12 for check in grid.values()),
                }.items() if condition]
                pup = execute_pup(before["markets"]["markets"], MARKETS, before["market_values"], baseline, requested=True)
                results.append({"fixture": fixture, "issues": issues, "sealed_at": sealed.isoformat(),
                                "forecast_at": cutoff.isoformat(), "form_diagnostics": observations[event],
                                "form": after["domestic_research"]["samples"], "difference": differences, "score_grid": grid,
                                "models": got, "component_research": before["component_research"],
                                "context_observations": before["observed_inputs"]["workload"],
                                "weather_observation": before["observed_inputs"]["prematch_weather_forecast"],
                                "pup": pup, "archived_tur2": before["tur2"],
                                "archived_auto_control": before["auto_control_by_market"]})
    verified, conflicts = {}, set()
    archive_history(args.work / "settlement-and-performance", [],
                    dt.datetime.now(dt.timezone.utc), verified_outcomes=verified, conflicts=conflicts)
    outcomes = [outcome for _, outcome, _ in verified.values()]
    packs = args.work / "prematch-and-research"
    frozen = json.loads(next((args.work / "frozen-candidates").glob("*/frozen-candidates.json")).read_bytes())
    forecasts = combine_forecasts(read_forecast_pack(receipt) for receipt in packs.glob("*/receipt.json")
                                  if (receipt.parent / "forecasts/forecasts.jsonl").is_file())
    eligible = select_evaluation_rows(frozen, forecasts)
    eligible = [row for row in eligible if row["event_id"] in verified]
    frozen_rows = join_holdout(eligible, outcomes) if eligible else []
    report = {"fixtures": len(cohort), "weights": WEIGHTS, "replayed": sum("models" in row for row in results),
              "issues": Counter(issue for row in results for issue in row["issues"]),
              "pup": Counter(row["pup"]["status"] for row in results if "pup" in row),
              "target_sealed_performance": settled_daily_pairs(packs, [row for row in outcomes if row["event_id"] in cohort]),
              "all_sealed_performance": settled_daily_pairs(packs, outcomes),
              "frozen_venue5_holdout": evaluate(frozen, frozen_rows) if frozen_rows else None,
              "frozen_venue5_holdout_weeks": len({utc(row["kickoff"]).date().isocalendar()[:2] for row in frozen_rows}),
              "records": results,
              "production_allowed": False}
    atomic_write(args.output, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())


if __name__ == "__main__":
    main()
