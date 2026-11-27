"""Joint feasibility and PUP triage for research marginals."""

from math import fsum, isfinite
from statistics import mean

from ex_decision import MARKETS
from ex_historical_features import market_labels

EPSILON = 1e-12


def reconcile(probabilities):
    """Construct one witness, and report which score events are unidentified."""
    if not all(type(p := probabilities.get(m)) in (int, float) and isfinite(p) and 0 <= p <= 1
               for m in MARKETS):
        return {"status": "INVALID_MARGINALS"}
    home, away, btts, over = (probabilities[m] for m in ("MS1", "MS2", "KG_VAR", "2.5_UST"))
    draw = 1 - home - away
    lower = max(0, btts + over - 1, btts - draw, over - home - away)
    upper = min(btts, over)
    issues = []
    if draw < -EPSILON:
        issues.append("MS1_PLUS_MS2_EXCEEDS_ONE")
    if btts - over > draw + EPSILON:
        issues.append("BTTS_WITHOUT_OVER_EXCEEDS_DRAW")
    if over - btts > home + away + EPSILON:
        issues.append("OVER_WITHOUT_BTTS_EXCEEDS_DECISIVE_RESULTS")
    if issues:
        return {"status": "INFEASIBLE", "issues": issues}

    # q is the intersection of BTTS and over. BTTS-only is necessarily 1–1.
    # Over-only is necessarily a shutout win. Draws occupy only 0–0, 1–1,
    # or BTTS+over. Each remaining band can be split across both win sides.
    q = (lower + upper) / 2
    btts_only, over_only, neither = btts - q, over - q, 1 - btts - over + q
    draw_both = (max(0, draw - btts_only - neither) + min(q, draw - btts_only)) / 2
    draw_neither = draw - btts_only - draw_both
    outcomes = {"0-0": draw_neither, "1-1": btts_only, "2-2": draw_both}
    for total, home_score, away_score in (
            (q - draw_both, "2-1", "1-2"),
            (over_only, "3-0", "0-3"),
            (neither - draw_neither, "2-0", "0-2")):
        home_share = home / (home + away) if home + away > 0 else 0
        outcomes[home_score] = total * home_share
        outcomes[away_score] = total * (1 - home_share)
    outcomes = {score: max(0, p) for score, p in outcomes.items()}
    marks = {score: market_labels(*map(int, score.split("-"))) for score in outcomes}
    derived = {market: fsum(p for score, p in outcomes.items() if marks[score][market]) for market in MARKETS}
    error = max(abs(1 - fsum(outcomes.values())), *(abs(derived[m] - probabilities[m]) for m in MARKETS))
    if error > EPSILON:
        raise ArithmeticError("Joint feasibility witness failed reconciliation")
    return {"status": "FEASIBLE", "witness_score_mass": outcomes, "derived": derived,
            "max_absolute_error": error, "point_scores_identified": False,
            "scenario_bounds": {"1-1": [max(0, btts - upper), max(0, btts - lower)],
                                "one_sided_3_plus": [max(0, over - upper), max(0, over - lower)],
                                **{key: [0, max(0, min(side, band))]
                                   for key, side, band in (
                                       ("2-0", home, 1 - btts - over + upper),
                                       ("0-2", away, 1 - btts - over + upper),
                                       ("3-0", home, over - lower), ("0-3", away, over - lower))}},
            "exact_score_outer_bounds_are_individual": True}


def validation_order(evaluation):
    """Select a complete model by mean validation Brier, never by test metrics."""
    return sorted(evaluation["models"], key=lambda name: (
        mean(data["validation"]["brier"] for data in evaluation["models"][name]["markets"].values()), name))


def research_pup(probabilities, joint, archived_reasons):
    """Allow one supported research candidate. Preserve unresolved comparisons."""
    reasons = {}
    for market in MARKETS:
        price = archived_reasons.get(market)
        probability = probabilities.get(market)
        if price == "PASS_ODDS_1_19_OR_LOWER":
            reasons[market] = "PASS_ODDS_1_19_OR_LOWER"
        elif joint.get("status") != "FEASIBLE":
            reasons[market] = "JOINT_DISTRIBUTION_UNAVAILABLE"
        elif probability < .70:
            reasons[market] = "BELOW_70_RESEARCH_THRESHOLD"
        else:
            reasons[market] = "RESEARCH_CANDIDATE"
    eligible = [m for m in MARKETS if reasons[m] == "RESEARCH_CANDIDATE"]
    return {"status": "SINGLE_RESEARCH_CANDIDATE" if len(eligible) == 1 else
            "REVIEW_REQUIRED" if eligible else "NO_RESEARCH_CANDIDATE",
            "selection": eligible[0] if len(eligible) == 1 else None,
            "eligible": eligible, "market_reasons": reasons, "archived_price_and_gate_reasons": archived_reasons,
            "goal_market_comparison": joint.get("scenario_bounds"),
            "probabilities_calibrated_for_production": False, "ex_final_allowed": False}
