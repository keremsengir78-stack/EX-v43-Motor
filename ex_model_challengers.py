"""Time-ordered model challengers. Outputs are research metrics only."""

import math
import random
from collections import defaultdict
from statistics import mean


def date_partitions(records):
    days = sorted({row[0] for row in records})
    if len(days) < 4:
        return None
    validation, test = days[len(days) // 2], days[3 * len(days) // 4]
    return (
        [row for row in records if row[0] < validation],
        [row for row in records if validation <= row[0] < test],
        [row for row in records if row[0] >= test],
    )


def sigmoid(logit):
    value = math.exp(-abs(logit))
    return 1 / (1 + value) if logit >= 0 else value / (1 + value)


def fit_offset(train, dimensions):
    """Penalized logistic offset, using damped coordinate Newton updates."""
    beta = [0.0] * dimensions
    for _ in range(100):
        largest = 0.0
        for col in range(dimensions):
            gradient = -beta[col]
            curvature = 1.0
            for logit, actual, features in train:
                p = sigmoid(logit + sum(b * x for b, x in zip(beta, features)))
                x = features[col]
                gradient += x * (actual - p)
                curvature += x * x * p * (1 - p)
            step = max(-1.0, min(1.0, gradient / curvature))
            beta[col] += step
            largest = max(largest, abs(step))
        if largest < 1e-7:
            break
    return beta


def compare_calibration(records, external=()):
    """Select on validation dates, then score a previously untouched final block."""
    partitions = date_partitions(records)
    if not partitions or min(map(len, partitions)) < 30 or len({r[2] for r in partitions[0]}) < 2:
        return {"status": "INSUFFICIENT_SAMPLE", "production_allowed": False}
    train, validation, test = partitions

    def features(rows, method):
        for _, probability, actual, workload in rows:
            p = min(1 - 1e-6, max(1e-6, probability))
            linear = math.log(p / (1 - p))
            x = {"intercept": (1.0,), "platt": (1.0, linear),
                 "platt_with_workload": (1.0, linear, *workload)}[method]
            yield linear, actual, x

    def losses(rows, method, beta):
        if method == "identity":
            return [(p - y) ** 2 for _, p, y, _ in rows]
        return [(sigmoid(logit + sum(b * x for b, x in zip(beta, xs))) - y) ** 2
                for logit, y, xs in features(rows, method)]

    fits = {"identity": []}
    for method in ("intercept", "platt", "platt_with_workload"):
        data = list(features(train, method))
        fits[method] = fit_offset(data, len(data[0][2]))
    validation_brier = {method: mean(losses(validation, method, beta)) for method, beta in fits.items()}
    # A negative Platt slope would invert baseline ranking and is inadmissible.
    for method in ("platt", "platt_with_workload"):
        if 1 + fits[method][1] < 0:
            del validation_brier[method]
    selected = min(validation_brier, key=validation_brier.get)
    reference_losses = losses(test, "identity", [])
    selected_losses = losses(test, selected, fits[selected])
    reference, final = mean(reference_losses), mean(selected_losses)
    weekly = defaultdict(list)
    for row, old, new in zip(test, reference_losses, selected_losses, strict=True):
        weekly[row[0].isocalendar()[:2]].append(new - old)
    blocks = list(weekly.values())
    uncertainty = None
    if len(blocks) >= 8:
        rng = random.Random(43)
        summaries = [(sum(block), len(block)) for block in blocks]
        draws = []
        for _ in range(1000):
            resampled = rng.choices(summaries, k=len(summaries))
            draws.append(sum(total for total, _ in resampled) / sum(n for _, n in resampled))
        draws.sort()
        uncertainty = [draws[25], draws[974]]
    # External forecasts start no earlier than the untouched domestic test.
    transferred = [row for row in external if row[0] >= min(r[0] for r in test)]
    transfer = {"eligible_n": len(transferred)}
    if len(transferred) >= 30:
        old = mean(losses(transferred, "identity", []))
        new = mean(losses(transferred, selected, fits[selected]))
        transfer.update(reference_brier=old, selected_brier=new, improved=new < old)
    return {
        "external_ucl_transfer": transfer,
        "train_n": len(train), "validation_n": len(validation), "test_n": len(test),
        "validation_start": min(r[0] for r in validation).isoformat(),
        "test_start": min(r[0] for r in test).isoformat(),
        "validation_brier": validation_brier, "selected_on_validation": selected,
        "test_reference_brier": reference, "test_selected_brier": final,
        "improved_on_final_test": final < reference, "production_allowed": False,
        "selected_minus_reference_week_bootstrap_95pct": uncertainty, "test_weeks": len(blocks),
    }
