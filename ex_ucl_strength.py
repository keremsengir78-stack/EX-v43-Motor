"""Opponent-adjusted league goal margins from corroborated UCL results."""

from collections import Counter, defaultdict
from statistics import mean


def fit_league_margins(matches, penalty=4):
    """Fit a home intercept and ridge-shrunk league effects in goal units."""
    opponents = defaultdict(list)
    for home, away, margin in matches:
        opponents[home]
        opponents[away]
        if home != away:
            opponents[home].append((away, margin, 1))
            opponents[away].append((home, -margin, -1))
    ratings = dict.fromkeys(sorted(opponents), 0.0)
    home_advantage = mean(margin for _, _, margin in matches)
    for _ in range(1000):
        updated = {
            league: sum(ratings[opponent] + margin - sign * home_advantage
                        for opponent, margin, sign in opponents[league]) / (len(opponents[league]) + penalty)
            for league in ratings
        }
        updated = {league: (ratings[league] + value) / 2 for league, value in updated.items()}
        intercept = mean(margin - updated[home] + updated[away] for home, away, margin in matches)
        if max(abs(updated[league] - ratings[league]) for league in ratings) < 1e-9:
            return updated, intercept
        ratings, home_advantage = updated, intercept
    raise ValueError("League margin fit did not converge")


def audit_league_margins(train, holdout):
    result = {
        "status": "BLOCKED_INSUFFICIENT_HOLDOUT",
        "train_matches": len(train), "holdout_matches": len(holdout),
        "goal_unit_penalty": 4, "calibrated": False, "ex_final_allowed": False,
    }
    if len(train) < 36 or len(holdout) < 12:
        return result
    counts = Counter(league for home, away, _ in train if home != away for league in (home, away))
    comparable = [(home, away, margin) for home, away, margin in holdout
                  if home != away and min(counts[home], counts[away]) >= 3]
    result["evaluated_matches"] = len(comparable)
    if len(comparable) < 12:
        return result
    ratings, intercept = fit_league_margins(train)
    null_intercept = mean(margin for _, _, margin in train)
    null_mse = mean((margin - null_intercept) ** 2 for _, _, margin in comparable)
    model_mse = mean((margin - intercept - ratings[home] + ratings[away]) ** 2
                     for home, away, margin in comparable)
    # A conservative alternative pools each league's signed goal residual
    # without simultaneously solving opponent effects.
    margins = defaultdict(list)
    for home, away, margin in train:
        if home != away:
            margins[home].append(margin - null_intercept)
            margins[away].append(null_intercept - margin)
    pooled = {league: sum(values) / (len(values) + 12) for league, values in margins.items()}
    pooled_mse = mean((margin - null_intercept - pooled[home] + pooled[away]) ** 2
                      for home, away, margin in comparable)
    result["pooled_residual_challenger"] = {
        "model_mse": pooled_mse, "better_than_reference": pooled_mse < null_mse,
        "method": "signed league residuals shrunk by twelve zero-margin observations",
    }
    result.update(null_mse=null_mse, model_mse=model_mse, training_cross_league_appearances=dict(counts))
    if model_mse >= null_mse:
        result["status"] = "BLOCKED_NO_HOLDOUT_IMPROVEMENT"
        return result
    full_ratings, _ = fit_league_margins([*train, *holdout])
    result.update(
        status="OBSERVED_LEAGUE_MARGIN_HOLDOUT_IMPROVED",
        league_margins={league: rating for league, rating in full_ratings.items() if counts[league] >= 3},
    )
    return result

def compare_league_challengers(train, validation, test):
    """Choose the margin model on an earlier round, evaluating once on the last."""
    if not train or not validation or not test:
        raise ValueError("Three chronological league samples are required")
    counts = Counter(league for home, away, _ in train if home != away for league in (home, away))
    leagues = {league for league, count in counts.items() if count >= 2}
    validation = [r for r in validation if r[0] in leagues and r[1] in leagues]
    test = [r for r in test if r[0] in leagues and r[1] in leagues]
    if min(len(validation), len(test)) < 12:
        return {"status": "INSUFFICIENT_LEAGUE_SUPPORT", "production_allowed": False}
    methods = {
        "home_only": ({}, mean(r[2] for r in train)),
        "ridge": fit_league_margins(train),
        "strong_ridge": fit_league_margins(train, penalty=16),
        "winsorized_ridge": fit_league_margins(
            [(home, away, max(-2, min(2, margin))) for home, away, margin in train]
        ),
    }

    def mse(model, sample):
        ratings, home_advantage = model
        return mean((margin - home_advantage - ratings.get(home, 0) + ratings.get(away, 0)) ** 2
                    for home, away, margin in sample)

    validation_mse = {name: mse(model, validation) for name, model in methods.items()}
    chosen = min(validation_mse, key=validation_mse.get)
    final = mse(methods[chosen], test)
    reference = mse(methods["home_only"], test)
    return {
        "train_n": len(train), "validation_n": len(validation), "test_n": len(test),
        "selected_on_validation": chosen, "validation_mse": validation_mse,
        "test_reference_mse": reference, "test_selected_mse": final,
        "improved_on_final_test": final < reference, "production_allowed": False,
    }
