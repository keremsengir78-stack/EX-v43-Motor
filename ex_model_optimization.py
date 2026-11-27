"""Offline candidates. Nothing here certifies an EX-G or changes selection gates."""

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from math import log, log1p
from random import Random
from statistics import mean
from time import perf_counter

from ex_component_experiment import weekly_interval
from ex_decision import MARKETS, WEIGHTS
from ex_model_challengers import date_partitions, fit_offset, sigmoid
from ex_research_components import FIELDS, metrics, vector, weather_vector

BLENDS = {
    "A": tuple(WEIGHTS[key] for key in ("team_strength", "match_conditions", "external_factors")),
    "B": (.60, .30, .10),
    "C": (.70, .25, .05),
}
REQUIRED = {"STAT_FORM": ("strength",), "STAT_WORKLOAD": ("strength", "kickoff_workload"),
            "STAT_VENUE5": ("short",), **{name: ("strength", "kickoff_workload", "external") for name in BLENDS}}


def predictors(row, market, inputs):
    return (1., *(value for key in inputs for value in
                  ((row[key][market],) if key in {"short", "strength"} else row[key])))


def score(model, row, market):
    if any(row.get(key) is None for key in REQUIRED[model["name"]]):
        return None
    def predict(keys, beta):
        return sigmoid(sum(a * b for a, b in zip(predictors(row, market, keys), beta, strict=True)))
    parameters = model["parameters"][market]
    if model["name"] in BLENDS:
        return sum(weight * probability for weight, probability in zip(
            BLENDS[model["name"]], (row["strength"][market],
                                    predict(("kickoff_workload",), parameters["workload"]),
                                    predict(("external",), parameters["external"])), strict=True))
    return predict(REQUIRED[model["name"]], parameters)


def fit(name, rows):
    model = {"name": name, "parameters": {}}
    inputs = REQUIRED[name]
    for market in MARKETS:
        if len({row["labels"][market] for row in rows}) != 2:
            return None
        def coefficients(keys):
            return fit_offset([(0., row["labels"][market], predictors(row, market, keys))
                               for row in rows], len(predictors(rows[0], market, keys)))
        model["parameters"][market] = (
            {"workload": coefficients(("kickoff_workload",)), "external": coefficients(("external",))}
            if name in BLENDS else coefficients(inputs)
        )
    model["trained_through"] = max(row["finished"] for row in rows).isoformat()
    return model


def measure(rows, prediction, market):
    labels = [row["labels"][market] for row in rows]
    values = [max(1e-12, min(1 - 1e-12, p)) for p in prediction]
    high = [y for p, y in zip(prediction, labels, strict=True) if p >= .70]
    report, losses = metrics([{"label": y} for y in labels], prediction)
    return {**report, "n": len(rows),
            "log_loss": mean(-log(p) if y else -log1p(-p) for p, y in zip(values, labels, strict=True)),
            "accuracy_at_50_pct": mean((p >= .5) == y for p, y in zip(prediction, labels, strict=True)),
            "predictions_at_least_70_pct": len(high), "hit_rate_at_least_70_pct": mean(high) if high else None}, losses


def block_uncertainty(rows, predictions, market):
    """Descriptive 95% intervals resampling whole UTC ISO weeks."""
    grouped = defaultdict(list)
    for row, probability in zip(rows, predictions, strict=True):
        grouped[row["kickoff"].isocalendar()[:2]].append((row, probability))
    weeks = list(grouped.values())
    if len(weeks) < 8:
        return {"weeks": len(weeks), "status": "INSUFFICIENT_WEEK_BLOCKS", "intervals": None}
    draws = defaultdict(list)
    rng = Random(43)
    for _ in range(1000):
        pairs = [pair for block in rng.choices(weeks, k=len(weeks)) for pair in block]
        sampled, p = zip(*pairs, strict=True)
        values, _ = measure(sampled, p, market)
        for key in ("brier", "log_loss", "ece_10_equal_width", "accuracy_at_50_pct", "hit_rate_at_least_70_pct"):
            if values[key] is not None:
                draws[key].append(values[key])
    intervals = {}
    for key, values in draws.items():
        # Do not condition a high-confidence interval on draws that happened to contain an alert.
        intervals[key] = [sorted(values)[25], sorted(values)[974]] if len(values) == 1000 else None
    intervals.setdefault("hit_rate_at_least_70_pct", None)
    return {"weeks": len(weeks), "status": "DESCRIPTIVE_HISTORICAL_ONLY", "intervals": intervals}


def evaluate(rows, names, training_universe=None, *, uncertainty=False):
    """All candidates share the same validation and test events in each comparison."""
    cohort = sorted((row for row in rows if all(row.get(key) is not None
                     for name in names for key in REQUIRED[name])), key=lambda row: row["kickoff"])
    parts = date_partitions([(row["kickoff"].date(), row) for row in cohort])
    result = {"eligible": len(cohort), "status": "INSUFFICIENT_SAMPLE", "models": {}}
    if not parts:
        return result
    train, validation, test = [[row for _, row in part] for part in parts]
    def partition_boundary(row):
        return datetime.combine(row["kickoff"].date(), datetime.min.time(), tzinfo=timezone.utc)
    validation_start, test_start = map(partition_boundary, (validation[0], test[0]))
    train = [row for row in train if row["finished"] < validation_start]
    validation = [row for row in validation if row["finished"] < test_start]
    result.update(splits=list(map(len, (train, validation, test))),
                  split_starts=[validation_start.isoformat(), test_start.isoformat()],
                  test_weeks=len({row["kickoff"].isocalendar()[:2] for row in test}))
    if min(result["splits"]) < 30:
        return result
    losses = {}
    for name in names:
        start = perf_counter()
        fitting = train if training_universe is None else [
            row for row in training_universe if row["kickoff"] < validation_start
            and row["finished"] < validation_start and all(row.get(key) is not None for key in REQUIRED[name])]
        if len(fitting) < 30 or (model := fit(name, fitting)) is None:
            continue
        by_market, losses[name] = {}, {}
        for market in MARKETS:
            predictions = [score(model, row, market) for row in test]
            test_result, losses[name][market] = measure(test, predictions, market)
            leagues = {}
            for league in sorted({row["league"] for row in test}):
                paired = [(row, p) for row, p in zip(test, predictions, strict=True) if row["league"] == league]
                league_rows, league_predictions = zip(*paired, strict=True)
                leagues[league] = measure(league_rows, league_predictions, market)[0]
            if uncertainty:
                test_result["weekly_uncertainty_95_pct"] = block_uncertainty(test, predictions, market)
            by_market[market] = {"validation": measure(validation, [score(model, row, market) for row in validation], market)[0],
                                 "test": test_result, "test_by_league": leagues}
        result["models"][name] = {"model": model, "markets": by_market, "fit_n": len(fitting),
                                   "seconds": perf_counter() - start}
    selected = {}
    if result["models"]:
        result["status"] = "EVALUATED_RESEARCH_ONLY"
        for market in MARKETS:
            baseline = next(iter(result["models"]))
            winner = min(result["models"], key=lambda name: result["models"][name]["markets"][market]["validation"]["brier"])
            interval = weekly_interval([(row["kickoff"].date(),) for row in test],
                                       losses[baseline][market], losses[winner][market])
            selected[market] = {"validation_choice": winner, "baseline": baseline,
                                "weekly_delta_brier_99_pct": interval,
                                "improvement_supported": len(test) >= 100 and interval is not None and interval[1] < 0}
    result["selected"] = selected
    return result


def historical_rows(examples, leagues, weather):
    rows = []
    cohorts = Counter()
    for row in examples:
        if not row["finished"] or row["finished"] <= row["kickoff"]:
            continue
        kickoff = row["kickoff"]
        observation = weather.get((row["event_id"], kickoff))
        external = weather_vector(observation, kickoff.isoformat(), kickoff - timedelta(microseconds=1))
        rows.append({**row, "external": vector(external, FIELDS["external_factors"]),
                     "league": leagues[row["event_id"]]})
        cohorts.update(key for key in ("strength", "kickoff_workload", "external") if rows[-1][key] is not None)
    return rows, dict(cohorts)
