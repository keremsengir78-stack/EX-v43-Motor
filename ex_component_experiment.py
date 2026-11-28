"""Chronological ablation of historical predictors against a calibrated reference."""

import math
import random
from collections import defaultdict
from statistics import mean

from ex_model_challengers import date_partitions, fit_offset, sigmoid


def component_vectors(features, market):
    home, away = features["home"], features["away"]
    if not home["venue_market_frequencies"] or not away["venue_market_frequencies"]:
        return None
    rates = tuple(side["venue_market_frequencies"][market] for side in (home, away))
    margins = tuple(side["venue_goal_difference_last_5"] - side["venue_goal_difference_last_10"]
                    for side in (home, away))
    rest = tuple(min(side["domestic_rest_calendar_days"], 14) / 14 for side in (home, away))
    loads = tuple(side["domestic_matches_last_14_days"] / 4 for side in (home, away))
    return {"venue_rates": rates, "recent_goal_form": margins, "domestic_workload": (*rest, *loads)}


def weekly_interval(rows, old, new):
    weeks = defaultdict(list)
    for row, baseline, candidate in zip(rows, old, new, strict=True):
        weeks[row[0].isocalendar()[:2]].append(candidate - baseline)
    if len(weeks) < 8:
        return None
    blocks = [(sum(values), len(values)) for values in weeks.values()]
    rng = random.Random(43)
    draws = []
    for _ in range(2000):
        sample = rng.choices(blocks, k=len(blocks))
        draws.append(sum(total for total, _ in sample) / sum(n for _, n in sample))
    draws.sort()
    # Two-sided 99% interval, conservative across four separately evaluated markets.
    return [draws[10], draws[1989]]


def evaluate_components(records, transfer=()):
    """Choose on validation dates. Neither fitting nor selection touches test outcomes."""
    parts = date_partitions(sorted(records, key=lambda row: row[0]))
    if not parts or min(map(len, parts)) < 30 or len({r[2] for r in parts[0]}) != 2:
        return {"status": "INSUFFICIENT_SAMPLE", "production_allowed": False}
    train, validation, test = parts
    groups = {
        "platt": (), "venue_rates": ("venue_rates",), "recent_goal_form": ("recent_goal_form",),
        "domestic_workload": ("domestic_workload",),
        "strength_and_workload": ("venue_rates", "recent_goal_form", "domestic_workload"),
    }

    def inputs(rows, group):
        for _, probability, actual, vectors in rows:
            p = min(1 - 1e-6, max(1e-6, probability))
            logit = math.log(p / (1 - p))
            yield logit, actual, (1.0, logit, *(x for name in group for x in vectors[name]))

    def losses(rows, method):
        if method == "identity":
            return [(probability - actual) ** 2 for _, probability, actual, _ in rows]
        return [(sigmoid(logit + sum(b * x for b, x in zip(beta[method], features))) - actual) ** 2
                for logit, actual, features in inputs(rows, groups[method])]

    beta = {}
    for name, group in groups.items():
        data = list(inputs(train, group))
        fit = fit_offset(data, len(data[0][2]))
        if 1 + fit[1] >= 0:
            beta[name] = fit
    valid = {name: mean(losses(validation, name)) for name in ("identity", *beta)}
    reference = min((name for name in ("identity", "platt") if name in valid), key=valid.get)
    selected = min(valid, key=valid.get)
    old, new = losses(test, reference), losses(test, selected)
    interval = weekly_interval(test, old, new)
    external = [row for row in transfer if row[0] >= test[0][0]]
    transfer_evaluation = {"eligible_n": len(external)}
    if len(external) >= 30:
        transfer_evaluation.update(
            reference_brier=mean(losses(external, reference)),
            selected_brier=mean(losses(external, selected)),
        )
    return {
        "train_n": len(train), "validation_n": len(validation), "test_n": len(test),
        "validation_start": validation[0][0].isoformat(), "test_start": test[0][0].isoformat(),
        "validation_brier": valid, "selected_on_validation": selected, "reference_on_validation": reference,
        "test_reference_brier": mean(old), "test_selected_brier": mean(new),
        "weekly_delta_brier_99pct": interval, "ucl_transfer": transfer_evaluation,
        "reliable_domestic_improvement": selected != reference and interval is not None and interval[1] < 0,
        "production_allowed": False,
    }
