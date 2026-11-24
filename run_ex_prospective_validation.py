"""Freeze research calibrators and evaluate an unseen chronological holdout."""

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

from ex_component_experiment import weekly_interval
from ex_history_archive import atomic_write, utc
from ex_model_challengers import fit_offset, sigmoid


MARKETS = ("KG_VAR", "2.5_UST")


def logit(p):
    if type(p) not in (int, float) or not 0 <= p <= 1:
        raise ValueError("Invalid forecast probability")
    p = min(1 - 1e-6, max(1e-6, p))
    return math.log(p / (1 - p))


def read_rows(raw):
    rows = [json.loads(line) for line in raw.splitlines() if line]
    ids = [row["event_id"] for row in rows]
    if not rows or len(ids) != len(set(ids)):
        raise ValueError("Empty or duplicate fixture cohort")
    return rows


def freeze(raw, frozen_at):
    rows = read_rows(raw)
    train = [row for row in rows if row["venue5_partition"] == "train"]
    if len(train) < 100:
        raise ValueError("Insufficient original training cohort")
    end = max(utc(row["finished"]) for row in train)
    validation_start = min(utc(row["kickoff"]) for row in rows if row["venue5_partition"] == "validation")
    if not end < validation_start < frozen_at:
        raise ValueError("Training observations cross validation or freeze cutoff")
    coefficients = {}
    for market in MARKETS:
        fit = []
        for row in train:
            value = logit(row["short"][market])
            actual = row["labels"][market]
            if type(actual) is not int or actual not in (0, 1):
                raise ValueError("Invalid outcome label")
            fit.append((value, actual, (1.0, value)))
        intercept, delta = fit_offset(fit, 2)
        if 1 + delta < 0:
            raise ValueError("Non-monotonic calibrator")
        coefficients[market] = [intercept, 1 + delta]
    return {"frozen_at": frozen_at.isoformat(), "training_n": len(train),
            "original_cohort_sha256": hashlib.sha256(raw).hexdigest(),
            "original_ids": sorted(row["event_id"] for row in rows),
            "original_last_kickoff": max(utc(row["kickoff"]) for row in rows).isoformat(),
            "coefficients": coefficients, "production_allowed": False}


def join_holdout(forecasts, outcomes):
    by_id = {row["event_id"]: row for row in outcomes}
    if len(by_id) != len(outcomes):
        raise ValueError("Duplicate outcomes")
    result = []
    for row in forecasts:
        if "labels" in row or "finished" in row:
            raise ValueError("Forecast ledger contains outcome information")
        actual = by_id.get(row["event_id"])
        if actual is None:
            continue
        if (utc(row["kickoff"]) != utc(actual["kickoff"]) or row["teams"] != actual["teams"]
                or utc(actual["settled_at"]) < utc(actual["finished"])):
            raise ValueError("Outcome fixture identity or capture mismatch")
        result.append({**row, "finished": actual["finished"], "labels": actual["labels"]})
    if not result:
        raise ValueError("No overlapping settled holdout outcomes")
    return result


def evaluate(model, rows):
    coefficients = model["coefficients"]
    if set(coefficients) != set(MARKETS) or any(
            len(pair) != 2 or any(type(value) not in (float, int) or not math.isfinite(value) for value in pair)
            or pair[1] < 0 for pair in coefficients.values()):
        raise ValueError("Only the frozen KG VAR and 2.5 ÜST monotonic candidates are admissible")
    seen = set(model["original_ids"])
    boundary = max(utc(model["original_last_kickoff"]), utc(model["frozen_at"]))
    for row in rows:
        kickoff = utc(row["kickoff"])
        if (row["event_id"] in seen or kickoff <= boundary
                or not boundary <= utc(row["forecast_at"]) < kickoff < utc(row["finished"])):
            raise ValueError("Holdout overlaps the original cohort or forecast is out of time")
        seen.add(row["event_id"])
    results = {}
    for market in (*MARKETS, "MS1", "MS2"):
        observations, reference, selected, strength_reference, strength_candidate = [], [], [], [], []
        for row in sorted(rows, key=lambda row: utc(row["kickoff"])):
            date = utc(row["kickoff"]).date()
            actual = row["labels"][market]
            if type(actual) is not int or actual not in (0, 1):
                raise ValueError("Invalid outcome label")
            base = row["short"][market]
            x = logit(base)
            if market in model["coefficients"]:
                offset, slope = model["coefficients"][market]
                observations.append((date,))
                reference.append((base - actual)**2)
                selected.append((sigmoid(offset + slope * x) - actual)**2)
            if row.get("strength") is not None:
                stronger = row["strength"][market]
                logit(stronger)
                strength_reference.append(((date,), (base - actual)**2))
                strength_candidate.append((stronger - actual)**2)
        def metrics(dates, original, candidate):
            interval = weekly_interval(dates, original, candidate) if original else None
            return {"n": len(original), "reference_brier": mean(original) if original else None,
                    "candidate_brier": mean(candidate) if candidate else None,
                    "weekly_delta_brier_99pct": interval,
                    "supported": len(original) >= 100 and interval is not None and interval[1] < 0}
        results[market] = {
            "calibration": metrics(observations, reference, selected) if market in MARKETS else "REFERENCE_ONLY",
            "fixed_strength": metrics([item[0] for item in strength_reference],
                                      [item[1] for item in strength_reference], strength_candidate),
        }
    return {"markets": results, "test_n": len(rows), "source_independence_certified": False,
            "production_allowed": False, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--examples", type=Path)
    mode.add_argument("--frozen-model", type=Path)
    parser.add_argument("--forecasts", type=Path)
    parser.add_argument("--outcomes", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.frozen_model:
        if not args.forecasts or not args.outcomes:
            parser.error("--forecasts and --outcomes are required with --frozen-model")
        result = evaluate(json.loads(args.frozen_model.read_text()),
                          join_holdout(read_rows(args.forecasts.read_bytes()), read_rows(args.outcomes.read_bytes())))
        artifact = result
    else:
        if args.forecasts or args.outcomes:
            parser.error("Forecasts and outcomes are only for frozen evaluation")
        artifact = freeze(args.examples.read_bytes(), dt.datetime.now(dt.timezone.utc))
        result = {"training_n": artifact["training_n"], "test_n": 0, "frozen_at": artifact["frozen_at"],
                  "holdout_status": "NO_LATER_SETTLED_AND_ARCHIVED_COHORT"}
    atomic_write(args.output, (json.dumps(artifact, indent=2) + "\n").encode())
    print(json.dumps(result))


if __name__ == "__main__":
    main()
