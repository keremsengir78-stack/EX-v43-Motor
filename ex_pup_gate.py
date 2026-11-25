"""Explicit post-analysis PUP comparison, with no inferred ranking rule."""

import math


def gate_pup(markets, expected, *, requested=False):
    issues = []
    for market in expected:
        record = markets.get(market, {}).get("ex_g", {})
        chance = record.get("probability")
        if (record.get("status") != "EX_G_AVAILABLE" or record.get("market") != market
                or type(chance) not in (int, float) or not math.isfinite(chance) or not 0 <= chance <= 1):
            issues.append(f"{market}:calibrated_probability_missing")
    return {"status": "BLOCKED" if requested is True else "NOT_REQUESTED", "issues": issues,
            "markets_checked": list(expected), "pup_allowed": False, "ex_final_allowed": False}


def score_scenarios(home, away):
    from ex_engine import distribution, poisson
    model = distribution(home, away)

    def one_sided(scoring_rate, blank_rate):
        return max(0, 1 - sum(poisson(k, scoring_rate) for k in range(3))) * poisson(0, blank_rate)

    home_only = one_sided(home, away)
    away_only = one_sided(away, home)
    return {
        "model": "INDEPENDENT_POISSON_RESEARCH",
        "exact_scores": {f"{h}-{a}": poisson(h, home) * poisson(a, away)
                         for h, a in ((1, 1), (2, 0), (0, 2), (3, 0), (0, 3), (2, 1), (1, 2), (2, 2))},
        "home_only_three_plus": home_only, "away_only_three_plus": away_only,
        "over25_only": home_only + away_only,
        "btts_only": model["p_11"],
        "both": max(0, model["btts"] - model["p_11"]),
        "neither": sum(poisson(h, home) * poisson(a, away)
                       for h, a in ((0, 0), (0, 1), (1, 0), (2, 0), (0, 2))),
        "exclusive_events": {
            "1-1": {"KG_VAR": True, "2.5_UST": False},
            "2-0": {"KG_VAR": False, "2.5_UST": False},
            "3-0": {"KG_VAR": False, "2.5_UST": True},
        },
    }


def execute_pup(markets, expected, odds_results, score_model, *, requested=False):
    state = gate_pup(markets, expected, requested=requested)
    if requested is not True:
        return state
    reasons, eligible = {}, []
    for market in expected:
        value = odds_results.get(market, {})
        lock = value.get("odds_lock", {})
        if lock.get("status") != "VERIFIED_INPUT":
            reasons[market] = "VERIFIED_PRICE_REQUIRED"
            state["issues"].append(f"{market}:verified_price_missing")
        elif lock.get("decision") == "PASS_ODDS_1_19_OR_LOWER":
            reasons[market] = "PASS_ODDS_1_19_OR_LOWER"
        elif value.get("bookmaker_implied_probability", 1) > 1 / 1.20:
            reasons[market] = "PRICE_BETWEEN_DEFINED_BANDS"
            state["issues"].append(f"{market}:price_rule_undefined")
        elif f"{market}:calibrated_probability_missing" in state["issues"]:
            reasons[market] = "CALIBRATED_EX_G_REQUIRED"
        else:
            eligible.append(market)
            reasons[market] = ("NEGATIVE_EX_D_IS_NOT_A_PASS_RULE"
                               if (value.get("ex_d") or 0) < 0 else "ELIGIBLE_FOR_COMPARISON")
    try:
        scenarios = score_scenarios(score_model["lambda_home"], score_model["lambda_away"])
    except (TypeError, KeyError, ValueError):
        scenarios = None
        state["issues"].append("pup:score_distribution_unavailable")
    state.update(market_reasons=reasons, score_scenarios=scenarios, eligible_markets=eligible, selection=None)
    if not state["issues"]:
        if not eligible:
            state["pup_allowed"] = True
            state["status"] = "PASS"
        elif len(eligible) == 1:
            state["pup_allowed"] = True
            state["status"] = "SINGLE_ELIGIBLE"
            state["selection"] = eligible[0]
        else:
            state["status"] = "REVIEW_REQUIRED"
            state["issues"].append("pup:no_approved_ordering_for_multiple_eligible_markets")
    return state
