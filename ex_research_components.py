"""Shared research-only component scoring and chronological evaluation."""

from collections import Counter, defaultdict
from datetime import timedelta
import json
import math
import re
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
    if not isinstance(observation, dict) or observation.get("kind") != "PREMATCH_NUMERICAL_FORECAST":
        return None
    stamp = utc(kickoff)
    source = observation.get("source")
    values = observation.get("values")
    if (not isinstance(source, dict) or not isinstance(values, dict)
            or not str(source.get("url", "")).startswith("https://api.open-meteo.com/v1/forecast?")
            or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256", "")))
            or observation.get("forecast_hour_utc") != stamp.strftime("%Y-%m-%dT%H:00:00Z")):
        return None
    try:
        if not utc(source["retrieved_at"]) < as_of < stamp:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    measurements = vector(tuple(values.get(key) for key in (
        "temperature_2m", "precipitation_probability", "wind_speed_10m")), FIELDS["external_factors"])
    if measurements is None or not 0 <= measurements[1] <= 100 or measurements[2] < 0:
        return None
    temperature, precipitation, wind = measurements
    return temperature / 30, precipitation / 100, wind / 50


def archive_weather(packs, as_of):
    """Select the latest sealed pre-kickoff forecast for each exact fixture."""
    selected = {}
    for path in packs.glob("*/forecasts/daily-analysis.json"):
        receipt = path.parent.parent / "receipt.json"
        sealed = utc(json.loads(receipt.read_bytes())["created_at"])
        if sealed >= as_of:
            continue
        for row in json.loads(path.read_bytes()):
            item = (row.get("observed_inputs") or {}).get("prematch_weather_forecast")
            if item is None:
                continue
            fixture = row["fixture"]
            kickoff = utc(fixture["kickoff_at"])
            captured = utc(row["as_of"])
            if captured >= sealed or sealed >= kickoff or weather_vector(item, kickoff.isoformat(), captured) is None:
                continue
            event = (fixture["event_id"], kickoff)
            if event not in selected or captured > selected[event][0]:
                selected[event] = captured, item
    return {event: item for event, (_, item) in selected.items()}


def metrics(rows, predictions):
    actual = [r["label"] for r in rows]
    bins = defaultdict(list)
    losses = []
    for probability, outcome in zip(predictions, actual, strict=True):
        losses.append((probability - outcome) ** 2)
        bins[min(9, int(10 * probability))].append((probability, outcome))
    error = sum(abs(sum(p - y for p, y in group)) for group in bins.values()) / len(actual)
    return {"brier": mean(losses), "ece_10_equal_width": error}, losses


def audit(facts, *, as_of=None, external_observations=None):
    by_competition = {record[1]: league for league, record in APPROVED_LEAGUES.items()}
    approved = [row for row in facts if row["competition"] in by_competition
                and (as_of is None or (row["kickoff"] < as_of and row["finished"] is not None
                                       and row["finished"] < as_of and row["captured_at"] < as_of))]
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
                observation = (external_observations or {}).get((row["event_id"], kickoff))
                if observation:
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
            train, validation, test = map(prepare, parts)
            if component != "team_strength":
                if len({r["label"] for r in train}) != 2:
                    continue
                coefficients = fit_offset([(0., r["label"], (1., *r["features"])) for r in train],
                                          FIELDS[component] + 1)
                parameters[component][market] = coefficients

            def evaluate(block):
                candidate = [r["strength"] for r in block] if component == "team_strength" else [
                    sigmoid(sum(b * v for b, v in zip(coefficients, (1., *r["features"]), strict=True)))
                    for r in block]
                reference, old = metrics(block, [r["reference"] for r in block])
                score, new = metrics(block, candidate)
                return {"candidate": score, "reference": reference,
                        "weekly_delta_brier_99pct": weekly_interval([(r["date"],) for r in block], old, new)}

            series["markets"][market] = {**evaluate(test), "validation": evaluate(validation)}
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
