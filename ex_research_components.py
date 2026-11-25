"""Shared research-only component scoring and chronological evaluation."""

from collections import Counter, defaultdict
import math
from statistics import mean

from ex_component_experiment import weekly_interval
from ex_decision import MARKETS, WEIGHTS, assess_markets
from ex_history_archive import utc
from ex_leagues import APPROVED_LEAGUES
from ex_model_challengers import date_partitions, fit_offset, sigmoid
from ex_retrospective import build_examples

FIELDS = {"match_conditions": 4, "external_factors": 3}


def vector(values, count):
    if isinstance(values, (list, tuple)) and len(values) == count and all(
            type(v) in (float, int) and math.isfinite(v) for v in values):
        return tuple(values)
    return None


def weather_vector(observation, kickoff, as_of):
    if not observation or observation.get("kind") != "PREMATCH_NUMERICAL_FORECAST":
        return None
    stamp = utc(kickoff)
    if (observation["forecast_hour_utc"] != stamp.strftime("%Y-%m-%dT%H:00:00Z")
            or not utc(observation["source"]["retrieved_at"]) < as_of < stamp):
        return None
    values = observation["values"]
    return vector((values["temperature_2m"] / 30, values["precipitation_probability"] / 100,
                   values["wind_speed_10m"] / 50), FIELDS["external_factors"])


def metrics(rows, predictions):
    actual = [r["label"] for r in rows]
    bins = defaultdict(list)
    losses = []
    for probability, outcome in zip(predictions, actual, strict=True):
        losses.append((probability - outcome) ** 2)
        bins[min(9, int(10 * probability))].append((probability, outcome))
    error = sum(abs(sum(p - y for p, y in group)) for group in bins.values()) / len(actual)
    return {"brier": mean(losses), "ece_10_equal_width": error}, losses


def audit(facts, *, external_observations=None):
    by_competition = {record[1]: league for league, record in APPROVED_LEAGUES.items()}
    approved = [row for row in facts if row["competition"] in by_competition]
    metadata = {row["event_id"]: row for row in approved}
    examples = build_examples(approved)
    reports, parameters = {}, {}
    for component in WEIGHTS:
        cohorts = []
        for row in examples:
            end = row["finished"]
            if component == "match_conditions":
                features = row["workload"]
            elif component == "external_factors":
                kickoff = row["kickoff"]
                observation = (external_observations or {}).get(row["event_id"])
                if observation:
                    from datetime import timedelta
                    features = weather_vector(observation, kickoff.isoformat(), kickoff - timedelta(microseconds=1))
                else:
                    features = None
            else:
                features = None
            if (end is None or end.date() != row["kickoff"].date()
                    or (component == "team_strength" and row["strength"] is None)
                    or (component in FIELDS and vector(features, FIELDS[component]) is None)):
                continue
            cohorts.append((row["kickoff"].date(), row, features))
        series = {"eligible": len(cohorts), "markets": {},
                  "by_league": dict(Counter(by_competition[metadata[row["event_id"]]["competition"]]
                                             for _, row, _ in cohorts))}
        reports[component] = series
        parts = date_partitions(cohorts)
        if not parts or min(map(len, parts)) < 30:
            series["status"] = "INSUFFICIENT_TIMESTAMPED_INPUTS_OR_SAMPLE"
            continue
        parameters[component] = {}
        series["status"] = "RESEARCH_EVALUATED"
        series["splits"] = dict(zip(("train", "validation", "test"), map(len, parts), strict=True))
        series["latest_training_finish"] = max(row["finished"] for _, row, _ in parts[0]).isoformat()
        for market in MARKETS:
            def prepare(block):
                return [{"date": day, "label": row["labels"][market],
                         "reference": row["short"][market] if component == "team_strength" else
                         (row["strength"] or row["short"])[market],
                         "strength": (row["strength"] or row["short"])[market],
                         "features": features} for day, row, features in block]
            train, _, test = map(prepare, parts)
            if component == "team_strength":
                candidate = [r["strength"] for r in test]
            else:
                if len({r["label"] for r in train}) != 2:
                    continue
                coef = fit_offset([(0., r["label"], (1., *r["features"])) for r in train],
                                  FIELDS[component] + 1)
                parameters[component][market] = coef
                candidate = [sigmoid(sum(b * v for b, v in zip(coef, (1., *r["features"]), strict=True)))
                             for r in test]
            ref, old = metrics(test, [r["reference"] for r in test])
            score, new = metrics(test, candidate)
            interval = weekly_interval([(r["date"],) for r in test], old, new)
            series["markets"][market] = {"candidate": score, "reference": ref,
                                         "weekly_delta_brier_99pct": interval}
    coverage = Counter(by_competition[row["competition"]] for row in approved)
    return {"archive_matches": len(facts), "approved_matches": len(approved), "examples": len(examples),
            "by_league": {league: coverage[league] for league in APPROVED_LEAGUES},
            "components": reports, "coefficients": parameters,
            "scope": "RETROSPECTIVE_RESEARCH", "production_allowed": False, "ex_final_allowed": False}


def score_components(strength, workload, weather, model, as_of):
    supplied = {"match_conditions": workload, "external_factors": weather}
    results = {}
    for market in MARKETS:
        components = {}
        for name, weight in WEIGHTS.items():
            score = strength.get(market) if name == "team_strength" and strength else None
            if name in FIELDS:
                vals = vector(supplied[name], FIELDS[name])
                info = (model or {}).get("components", {}).get(name, {})
                beta = vector((model or {}).get("coefficients", {}).get(name, {}).get(market), FIELDS[name] + 1)
                if vals is not None and beta is not None and utc(info["latest_training_finish"]) < as_of:
                    score = sigmoid(sum(b * v for b, v in zip(beta, (1., *vals), strict=True)))
            components[name] = {"score": score, "weight": weight,
                                "status": "RESEARCH_ONLY" if score is not None else "MISSING_INPUTS_OR_MODEL"}
        complete = all(part["score"] is not None for part in components.values())
        results[market] = {"components": components, "weighted_research_score":
                           sum(part["score"] * part["weight"] for part in components.values()) if complete else None}
    # Production only accepts separately certified component evidence.
    uncertified = {market: {name: {"score": part["score"], "verified": False}
                            for name, part in row["components"].items() if part["score"] is not None}
                   for market, row in results.items()}
    return results, assess_markets(uncertified, as_of=as_of.isoformat())
