"""Time-ordered, research-only model discrimination and score forecasting."""

from collections import Counter, defaultdict
from math import log
from statistics import mean, pstdev
from time import perf_counter

from ex_decision import MARKETS
from ex_historical_features import market_labels
from ex_model_challengers import date_partitions, fit_offset, sigmoid
from ex_model_optimization import block_uncertainty, fit, measure, score
from ex_performance_v1 import DOMESTIC, KEYS, forecast, intensity, replay, score_model
from ex_retrospective import build_examples
from ex_component_experiment import weekly_interval
from ex_leagues import season_bounds


def features(facts, targets, *, archived=False):
    """Update ratings and venue observations only from results available at cutoff."""
    eligible = [f for f in facts if f["finished"] and f["score"] is not None
                and f["competition"] in DOMESTIC]
    key = (lambda r: max(r["finished"], r["captured_at"])) if archived else (lambda r: r["finished"])
    pending = iter(sorted(eligible, key=lambda r: (key(r), r["kickoff"], r["event_id"])))
    prior = next(pending, None)
    ratings, venue, league = defaultdict(dict), defaultdict(list), defaultdict(list)
    league_results = defaultdict(Counter)
    for target in sorted(targets, key=lambda t: (t.get("as_of", t["kickoff"]), t["event_id"])):
        cutoff = target.get("as_of", target["kickoff"])
        while prior is not None and key(prior) < cutoff:
            comp = prior["competition"]
            h, a = (prior["teams"][side] for side in ("home", "away"))
            hg, ag = prior["score"]
            hr, ar = (ratings[comp].get(club, 1500.) for club in (h, a))
            expected = 1 / (1 + 10 ** ((ar - hr - 60) / 400))
            shift = 20 * ((1 if hg > ag else .5 if hg == ag else 0) - expected)
            ratings[comp].update({h: hr + shift, a: ar - shift})
            venue[comp, h, "home"].append((prior["kickoff"], hg, ag, ar))
            venue[comp, a, "away"].append((prior["kickoff"], ag, hg, hr))
            league[comp].append((prior["kickoff"], hg, ag))
            league_results[comp].update(market_labels(hg, ag))
            prior = next(pending, None)
        comp = target["competition"]
        if comp not in DOMESTIC:
            continue
        league_rows = league[comp]
        season = season_bounds(DOMESTIC[comp], target["kickoff"].date())[0]
        if len(league_rows) < 30:
            continue
        base = [mean(r[i] for r in league_rows) for i in (1, 2)]
        if min(base) <= 0:
            continue
        clubs = [target["teams"][side] for side in ("home", "away")]
        samples = [sorted(venue[comp, club, side])[-5:]
                   for club, side in zip(clubs, ("home", "away"), strict=True)]
        if min(map(len, samples)) < 5:
            continue
        rates = [[mean(r[i] for r in sample) for i in (1, 2)] for sample in samples]
        # Opponent quality is aggregated separately. Elo is trained only once
        # per match, and attack/defence use raw goals instead of a second Elo correction.
        opponent = [(mean(r[3] for r in sample) - 1500) / 400 for sample in samples]
        diff = (ratings[comp][clubs[0]] - ratings[comp][clubs[1]]) / 400
        long = []
        for club, side in zip(clubs, ("home", "away"), strict=True):
            history = sorted(venue[comp, club, side])
            recent = history[-10:-5]
            # Keep season evidence disjoint from the ten same-venue games.
            opposite = "away" if side == "home" else "home"
            older_season = [r for r in (*history[:-10], *venue[comp, club, opposite])
                            if r[0].date() >= season]
            long.append([tuple(mean(r[c] for r in rows) for c in (1, 2)) if rows else None
                         for rows in (recent, older_season)])
        # A venue-rate Poisson baseline with documented league-prior regularization.
        shrunk = [[(n * rate + 5 * base[(i + side) % 2]) / (n + 5)
                   for i, rate in enumerate(pair)] for side, (n, pair) in enumerate(zip(map(len, samples), rates))]
        home = intensity(shrunk[0][0] * shrunk[1][1] / base[0])
        away = intensity(shrunk[1][0] * shrunk[0][1] / base[1])
        yield target["event_id"], {"goal_rates": (home, away), "venue_goals": (*rates[0], *rates[1]),
            "elo": (diff, *opponent), "disjoint_supplemental_windows": long,
            "league_rates": {m: league_results[comp][m] / len(league_rows) for m in MARKETS}}


def as_markets(grid):
    return {market: grid[key] for market, key in KEYS.items()}


def prepare(facts):
    facts = [{**row, "finished": max(row["finished"], row["captured_at"])}
             if row.get("evidence_scope") == "ESPN_SCOREBOARD_RESEARCH" and row["finished"] else row
             for row in facts]
    examples = {row["event_id"]: row for row in build_examples(facts)}
    targets = [r for r in facts if r["finished"] and r["score"] is not None and r["competition"] in DOMESTIC]
    new = dict(features(facts, targets))
    ref = {r["event_id"]: form for r, form in replay(facts, targets)}
    common = []
    for r in targets:
        event = r["event_id"]
        prev = examples.get(event)
        if event in new and event in ref and prev and prev["strength"] and prev["kickoff_workload"]:
            common.append({**prev, **new[event], "league": DOMESTIC[r["competition"]],
                           "form": ref[event], "goals": r["score"]})
    return common, {"target_scores": len(targets), "venue_goal_models": len(new),
                    "reference_v1": len(ref), "common": len(common)}


def extended_available(row):
    return all(window is not None for side in row["disjoint_supplemental_windows"] for window in side)


def predictors(row, model):
    if model in {"ELO", "ELO_EXTENDED"}:
        values = (1., *row["elo"], *row["goal_rates"], *row["kickoff_workload"])
        if model == "ELO_EXTENDED":
            return (*values, *(v for side in row["disjoint_supplemental_windows"] for window in side for v in window))
        return values
    return (1., *row["venue_goals"])


def train_models(train, validation):
    parameters = {"stats": {}, "logistic": {}}
    for name in ("STAT_FORM", "STAT_WORKLOAD", "STAT_VENUE5"):
        parameters["stats"][name] = fit(name, train)
    extended = [row for row in train if extended_available(row)]
    for name, cohort in (("ELO", train), ("VENUE5_GOALS", train), ("ELO_EXTENDED", extended)):
        if len(cohort) >= 30 and all(len({r["labels"][m] for r in cohort}) == 2 for m in MARKETS):
            parameters["logistic"][name] = {m: fit_offset(
                [(0., r["labels"][m], predictors(r, name)) for r in cohort],
                len(predictors(cohort[0], name))) for m in MARKETS}
    parameters["extended_train_n"] = len(extended)
    scales = [sum(r["goals"][i] for r in train) / sum(r["goal_rates"][i] for r in train) for i in (0, 1)]
    parameters["scales"] = scales
    def rho_loss(rho):
        losses = []
        for row in train:
            h, a = (intensity(p * f) for p, f in zip(row["goal_rates"], scales, strict=True))
            g = tuple(row["goals"])
            tau = {(0, 0): 1-h*a*rho, (0, 1): 1+h*rho, (1, 0): 1+a*rho, (1, 1): 1-rho}.get(g, 1)
            effective_rho = max(-min(1/h, 1/a), min(rho, 1, 1/(h*a)))
            if effective_rho != rho:
                tau = {(0, 0): 1-h*a*effective_rho, (0, 1): 1+h*effective_rho,
                       (1, 0): 1+a*effective_rho, (1, 1): 1-effective_rho}.get(g, 1)
            losses.append(-log(max(1e-12, tau)))
        return mean(losses)
    parameters["rho"] = min((-.20, -.12, -.08, -.04, 0., .04, .08), key=rho_loss)
    v1_settings = [(0., shrink, rho, scale) for shrink in (.5, 1.)
                   for rho in (0., -.08) for scale in (1., max(.8, min(1.2, mean(scales))))]
    parameters["v1"] = min(v1_settings, key=lambda settings: mean(
        (p - row["labels"][market])**2 for row in validation
        for market, p in as_markets(forecast(row["form"], settings)[1]).items()))
    pairs = []
    for row in validation:
        a = as_markets(forecast(row["form"], parameters["v1"])[0])
        rates = [intensity(p * f) for p, f in zip(row["goal_rates"], scales, strict=True)]
        b = as_markets(score_model(*rates, parameters["rho"]))
        pairs.append((a, b, row["labels"]))
    parameters["hybrid_ex_weight"] = min((.25, .5, .75), key=lambda weight: mean(
        (weight*a[m] + (1-weight)*b[m] - labels[m])**2 for a,b,labels in pairs for m in MARKETS))
    return parameters


def predict(row, model):
    result = {"LEAGUE": row["league_rates"]}
    grids = {}
    rates = [intensity(p * f) for p, f in zip(row["goal_rates"], model["scales"], strict=True)]
    grids["POISSON"] = score_model(*rates, 0.)
    grids["DIXON_COLES"] = score_model(*rates, model["rho"])
    if row.get("form"):
        grids["EX_REFERENCE"], grids["V1"] = forecast(row["form"], model["v1"])
        weight = model["hybrid_ex_weight"]
        result["HYBRID"] = {m: weight * grids["EX_REFERENCE"][k] + (1-weight) * grids["DIXON_COLES"][k]
                            for m, k in KEYS.items()}
    for name, params in model["stats"].items():
        if params and all(score(params, row, m) is not None for m in MARKETS):
            result[name] = {m: score(params, row, m) for m in MARKETS}
    for name, params in model["logistic"].items():
        if name.startswith("ELO") and row.get("kickoff_workload") is None:
            continue
        if name == "ELO_EXTENDED" and not extended_available(row):
            continue
        result[name] = {m: sigmoid(sum(b*x for b, x in zip(params[m], predictors(row, name), strict=True)))
                        for m in MARKETS}
    result.update({name: as_markets(grid) for name, grid in grids.items()})
    return result, grids


def evaluate(rows):
    rows = sorted(rows, key=lambda r:r["kickoff"])
    parts = date_partitions([(r["kickoff"].date(), r) for r in rows])
    if not parts:
        raise ValueError("Insufficient chronological dates")
    train, validation, test = [[r for _, r in block] for block in parts]
    train = [r for r in train if r["finished"].date() < validation[0]["kickoff"].date()]
    validation = [r for r in validation if r["finished"].date() < test[0]["kickoff"].date()]
    if min(map(len, (train, validation, test))) < 30:
        raise ValueError("Insufficient separated matches")
    model = train_models(train, validation)
    report = {"splits": [len(train), len(validation), len(test)], "train_through": max(r["finished"] for r in train).isoformat(),
              "validation_through": max(r["finished"] for r in validation).isoformat(), "test_start": test[0]["kickoff"].isoformat(), "test_dates": sorted({r["kickoff"].date().isoformat() for r in test}),
              "markets": {}, "parameters": model, "production_allowed": False}
    start = perf_counter()
    valid_predictions = [predict(row, model)[0] for row in validation]
    test_predictions = [predict(row, model)[0] for row in test]
    report["prediction_seconds"] = perf_counter() - start
    for m in MARKETS:
        comparison, losses = {}, {}
        for name in (x for x in test_predictions[0] if x != "ELO_EXTENDED"):
            p = [x[name][m] for x in test_predictions]
            val = [x[name][m] for x in valid_predictions]
            stats, losses[name] = measure(test, p, m)
            groups = defaultdict(list)
            for row, probability in zip(test, p, strict=True):
                groups[row["league"]].append((row, probability))
            ties = Counter(p)
            nontied = [loss for loss, x in zip(losses[name], p, strict=True) if ties[x] == 1]
            high = [(x, r["labels"][m]) for r, x in zip(test, p, strict=True) if x >= .70]
            stats.update(high_mean_probability=mean(x for x,_ in high) if high else None,
                         high_calibration_gap=mean(x-y for x,y in high) if high else None,
                         non_tie_subset_brier=mean(nontied) if nontied else None,
                         observed_rate=mean(r["labels"][m] for r in test), probability_stddev=pstdev(p),
                         distinct_probabilities=len(ties), min_probability=min(p), max_probability=max(p),
                         tied_predictions=sum(n for n in ties.values() if n > 1),
                         tie_subset_brier=mean(l for l, x in zip(losses[name], p, strict=True) if ties[x]>1)
                         if any(n>1 for n in ties.values()) else None,
                         weekly_uncertainty=block_uncertainty(test,p,m))
            comparison[name] = {"validation": measure(validation, val, m)[0], "test": stats,
                                "by_league": {key: measure(*zip(*part), m)[0] for key,part in groups.items()}}
        winner = min(comparison, key=lambda key:comparison[key]["validation"]["brier"])
        ci = weekly_interval([(r["kickoff"].date(),) for r in test], losses["EX_REFERENCE"], losses[winner])
        report["markets"][m] = {"validation_choice":winner,"models":comparison,"weekly_delta_brier_99pct_vs_ex":ci}
        extended = {}
        for label, partition, predictions in (("validation", validation, valid_predictions), ("test", test, test_predictions)):
            subset = [(r, p) for r,p in zip(partition, predictions, strict=True) if "ELO_EXTENDED" in p]
            if subset:
                subset_rows, predictions = zip(*subset, strict=True)
                extended[label] = {name: measure(subset_rows, [p[name][m] for p in predictions], m)[0]
                                   for name in ("ELO", "ELO_EXTENDED", "EX_REFERENCE")}
        report["markets"][m]["extended_exploratory_subset"] = extended
    return report
