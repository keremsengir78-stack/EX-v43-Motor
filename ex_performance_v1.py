"""Research-only opponent-adjusted score replay and paired market evaluation."""

from collections import Counter, defaultdict
import json
import math
from statistics import mean

from ex_engine import W, distribution, poisson, weighted_form
from ex_historical_features import market_labels
from ex_history_archive import utc
from ex_leagues import APPROVED_LEAGUES, CUP_HISTORY_SLUGS, UEFA_CUPS, season_bounds
from ex_model_challengers import date_partitions, fit_offset, sigmoid
from ex_research_components import metrics
from ex_ucl_strength import fit_league_margins
from ex_component_experiment import weekly_interval

REFERENCE = "EX-V43-POISSON"
CANDIDATE = "EX-V43-PERFORMANCE-V1"
EUROPE = {"uefa.champions", "uefa.europa", "uefa.europa.conf", "uefa.europa.conference"}
DOMESTIC = {record[1]: league for league, record in APPROVED_LEAGUES.items() if league not in UEFA_CUPS}
SUPPORT = {slug: league for league, slug in CUP_HISTORY_SLUGS.items()}
KEYS = {"2.5_UST": "over25", "KG_VAR": "btts", "MS1": "home_win", "MS2": "away_win"}


def intensity(value):
    return min(5., max(.05, value))


def score_model(home, away, dependence):
    home_mass = [poisson(k, home) for k in range(30)]
    away_mass = [poisson(k, away) for k in range(30)]
    # Dixon-Coles changes only the four low-score cells. Nonnegative factors
    # preserve total mass and the two Poisson marginals.
    rho = max(-min(1 / home, 1 / away), min(dependence, 1, 1 / (home * away)))
    factors = {(0, 0): 1 - home * away * rho, (0, 1): 1 + home * rho,
               (1, 0): 1 + away * rho, (1, 1): 1 - rho}
    grid = [(h, a, p * q * factors.get((h, a), 1))
            for h, p in enumerate(home_mass) for a, q in enumerate(away_mass)]
    cells = {(h, a): p for h, a, p in grid}
    return {
        "over25": sum(p for h, a, p in grid if h + a >= 3),
        "btts": sum(p for h, a, p in grid if h and a),
        "home_win": sum(p for h, a, p in grid if h > a),
        "away_win": sum(p for h, a, p in grid if h < a),
        "draw": sum(p for h, a, p in grid if h == a),
        "score_scenarios": {f"{h}-{a}": cells[h, a] for h, a in ((1, 1), (2, 0), (0, 2), (3, 0), (0, 3))},
        "one_side_three_plus": sum(p for h, a, p in grid if min(h, a) == 0 and max(h, a) >= 3),
        "top_scores": [(f"{h}-{a}", p) for h, a, p in sorted(grid, key=lambda cell: -cell[2])[:8]],
        "lambda_home": home, "lambda_away": away, "probability_mass": sum(cells.values()),
    }


class History:
    """Incorporate only results settled before the prediction's cutoff."""

    def __init__(self):
        self.games = defaultdict(list)
        self.membership = defaultdict(dict)
        self.team_margin = defaultdict(float)
        self.europe = []
        self._league_fit = (0, {}, {})

    def league(self, team, day, *, allow_support=False):
        active = [league for league, last in self.membership[team].items()
                  if (allow_support or league in APPROVED_LEAGUES) and season_bounds(league, day)[0] <= last < day]
        return active[0] if len(active) == 1 else None

    def update(self, fact):
        home, away = (fact["teams"][side] for side in ("home", "away"))
        hg, ag = fact["score"]
        day = fact["kickoff"].date()
        league = DOMESTIC.get(fact["competition"]) or SUPPORT.get(fact["competition"])
        if fact["competition"] in EUROPE:
            hl, al = self.league(home, day), self.league(away, day)
            if hl and al and hl != al:
                self.europe.append((hl, al, hg - ag))
        elif league:
            row = dict(date=day, league=league, home=home, away=away, hg=hg, ag=ag,
                       home_opponent=self.team_margin[league, away], away_opponent=self.team_margin[league, home])
            for club in (home, away):
                self.games[league, club].append(row)
                last = self.membership[club].get(league, day)
                self.membership[club][league] = max(last, day)
            # Forecast the goal margin from prior ratings. Limit the influence
            # of single blowouts and center the home advantage at half a goal.
            residual = max(-3, min(3, hg - ag - .5 - self.team_margin[league, home] + self.team_margin[league, away]))
            self.team_margin[league, home] += .08 * residual
            self.team_margin[league, away] -= .08 * residual

    def league_coefficients(self):
        if len(self.europe) != self._league_fit[0]:
            ratings, _ = fit_league_margins(self.europe, penalty=16)
            counts = Counter(league for record in self.europe for league in record[:2])
            self._league_fit = (len(self.europe), ratings, dict(counts))
        return self._league_fit[1:]

    def form(self, team, side, league, day):
        rows = sorted(self.games[league, team], key=lambda row: row["date"])
        season, previous = season_bounds(league, day)
        raw, audit = weighted_form(rows, team, side, day, league, season, previous)
        if raw is None or audit["counts"][:2] != [5, 10]:
            return None
        venue = [r for r in rows if r["date"] < day and r[side] == team]
        windows = (venue[-5:], venue[-10:], [r for r in rows if season <= r["date"] < day],
                   [r for r in venue if previous <= r["date"] < season])

        def adjustment(group):
            return mean(r["home_opponent"] if r["home"] == team else r["away_opponent"] for r in group)

        adjusted = []
        for window, (scored, conceded) in zip(windows, audit["rates"], strict=True):
            margin = adjustment(window) / 2
            adjusted.append((max(0., scored + margin), max(0., conceded - margin)))
        quality = tuple(mean((adjusted[2][i], adjusted[3][i])) for i in range(2))
        form = tuple(sum(w * rates[i] for w, rates in zip(W, adjusted, strict=True)) for i in range(2))
        return raw, form, quality

    def features(self, fact, exclusions=None):
        home, away = (fact["teams"][side] for side in ("home", "away"))
        day = fact["kickoff"].date()
        if fact["competition"] in EUROPE:
            support = fact["competition"] != "uefa.champions"
            hl, al = self.league(home, day, allow_support=support), self.league(away, day, allow_support=support)
        elif fact["competition"] in DOMESTIC:
            hl = al = DOMESTIC[fact["competition"]]
        else:
            if exclusions is not None:
                exclusions["unsupported_target_competition"] += 1
            return None
        if not hl or not al:
            if exclusions is not None:
                exclusions["missing_or_ambiguous_domestic_league"] += 1
            return None
        h, a = self.form(home, "home", hl, day), self.form(away, "away", al, day)
        if not h or not a:
            if exclusions is not None:
                exclusions["incomplete_team_form_windows"] += 1
            return None
        ratings, counts = self.league_coefficients()
        margin = ratings[hl] - ratings[al] if hl != al and min(counts.get(hl, 0), counts.get(al, 0)) >= 3 else None
        return h, a, margin


def replay(facts, targets, *, exclusions=None):
    history = History()
    settled = iter(sorted((r for r in facts if r["score"] is not None and r["finished"] is not None),
                          key=lambda row: (row["finished"], row["kickoff"], row["event_id"])))
    prior = next(settled, None)
    for row in sorted(targets, key=lambda row: (row.get("as_of", row["kickoff"]), row["event_id"])):
        cutoff = row.get("as_of", row["kickoff"])
        while prior and prior["finished"] < cutoff:
            history.update(prior)
            prior = next(settled, None)
        features = history.features(row, exclusions)
        if features:
            yield row, features


def forecast(features, setting):
    h, a, margin = features
    strength, shrink, dependence, total_scale = setting
    # Attenuate the opponent correction uniformly across the four fixed windows.
    left = [h[0][i] + shrink * (h[1][i] - h[0][i]) for i in range(2)]
    right = [a[0][i] + shrink * (a[1][i] - a[0][i]) for i in range(2)]
    shift = strength * (margin or 0.) / 2
    original = distribution(intensity((h[0][0] + a[0][1]) / 2), intensity((a[0][0] + h[0][1]) / 2))
    adjusted = score_model(intensity(total_scale * (left[0] + right[1]) / 2 + shift),
                           intensity(total_scale * (right[0] + left[1]) / 2 - shift), dependence)
    return original, adjusted


def measure(rows):
    output = {}
    for market, key in KEYS.items():
        labels = [{"label": row["labels"][market]} for row in rows]
        report = {}
        losses = []
        for version in (REFERENCE, CANDIDATE):
            probabilities = [row[version][key] for row in rows]
            result, squared = metrics(labels, probabilities) if rows else ({}, [])
            losses.append(squared)
            if rows:
                actual = [r["label"] for r in labels]
                result.update(log_loss=-mean(math.log(max(1e-12, p if y else 1 - p))
                                             for p, y in zip(probabilities, actual, strict=True)),
                              accuracy_at_half=mean((p >= .5) == bool(y)
                                                    for p, y in zip(probabilities, actual, strict=True)))
                result["thresholds"] = {}
                for threshold in (.65, .70, .75, .80):
                    selected = [y for p, y in zip(probabilities, actual, strict=True) if p > threshold]
                    result["thresholds"][str(threshold)] = {"n": len(selected), "hit_rate": mean(selected) if selected else None}
            report[version] = result
        report["paired_weekly_brier_delta_99pct"] = weekly_interval([(r["date"],) for r in rows], *losses)
        output[market] = report
    return output


def calibration_candidates(train, validation, test):
    """Fit research-probability mappings on training and select only on validation."""
    report = {"scope": "RECONSTRUCTED_BASELINE_PROBABILITIES", "production_allowed": False,
              "test_samples": len(test), "test_weeks": len({r["date"].isocalendar()[:2] for r in test}),
              "markets": {}}
    for market, key in KEYS.items():
        report["markets"][market] = {}
        for version in (REFERENCE, CANDIDATE):
            def inputs(rows):
                for row in rows:
                    probability = min(1 - 1e-6, max(1e-6, row[version][key]))
                    yield math.log(probability / (1 - probability)), row["labels"][market]

            training = list(inputs(train))
            if len({outcome for _, outcome in training}) < 2:
                continue
            fits = {"identity": (0., 0.)}
            for method, dimensions in (("intercept", 1), ("platt", 2)):
                offset = fit_offset([(logit, y, (1., logit)[:dimensions]) for logit, y in training], dimensions)
                intercept, change = (*offset, 0.) if dimensions == 1 else offset
                if 1 + change > 0:
                    fits[method] = intercept, change

            def calibrated(rows, method):
                if method == "identity":
                    return [row[version][key] for row in rows]
                intercept, change = fits[method]
                return [sigmoid(intercept + (1 + change) * logit) for logit, _ in inputs(rows)]

            def evaluation(rows, method):
                labels = [{"label": row["labels"][market]} for row in rows]
                predictions = calibrated(rows, method)
                result, losses = metrics(labels, predictions)
                result["log_loss"] = -mean(math.log(max(1e-12, p if y["label"] else 1 - p))
                                           for p, y in zip(predictions, labels, strict=True))
                return result, losses

            scores = {method: evaluation(validation, method)[0]["brier"] for method in fits}
            selected = min(scores, key=scores.get)
            reference, old = evaluation(test, "identity")
            candidate, new = evaluation(test, selected)
            report["markets"][market][version] = {
                "selected_on_validation": selected, "validation_brier": scores,
                "test_reference": reference, "test_candidate": candidate,
                "paired_weekly_brier_delta_99pct": weekly_interval([(row["date"],) for row in test], old, new),
            }
    return report


def experiment(facts):
    scored = [r for r in facts if r["score"] is not None and r["finished"] is not None]
    eligible = [r for r in scored if r["finished"].date() == r["kickoff"].date()]
    overnight = [r for r in scored if r["finished"].date() > r["kickoff"].date()
                 and r.get("terminal_source") == "PROVIDER_END_REGULAR_TIME"]
    exclusions = Counter()
    examples = [(r["kickoff"].date(), r, f) for r, f in replay(facts, eligible, exclusions=exclusions)]
    parts = date_partitions(examples)
    overnight_examples = sum(1 for _ in replay(facts, overnight)) if overnight else 0
    result = {"eligible": len(examples), "production_allowed": False,
              "cohort_flow": {"archive_records": len(facts),
                              "excluded_missing_score_or_finish": len(facts) - len(scored),
                              "excluded_non_same_day_finish": len(scored) - len(eligible),
                              "non_same_day_completion_by_provenance": dict(Counter(
                                  r.get("terminal_source") or r.get("evidence_scope") or "UNSPECIFIED"
                                  for r in scored if r["finished"].date() != r["kickoff"].date())),
                              "excluded_no_complete_prematch_replay": len(eligible) - len(examples),
                              "replay_exclusions": dict(exclusions),
                              "overnight_provider_terminal_records": len(overnight),
                              "overnight_complete_replays_research_only": overnight_examples}}
    if not parts:
        return result
    train, valid, test = parts

    def records(part, setting):
        return [dict(date=day, labels=market_labels(*r["score"]), **dict(zip(
                    (REFERENCE, CANDIDATE), forecast(f, setting), strict=True)))
                for day, r, f in part]

    # Estimate the total-goal scale on training labels only. Margin shifts and
    # the low-score correction alone cannot materially change Over 2.5.
    training_goals = sum(sum(r["score"]) for _, r, _ in train)
    expected_goals = sum(sum(pair[0]) / 2 for _, _, features in train for pair in features[:2])
    trained_scale = max(.8, min(1.2, training_goals / expected_goals)) if expected_goals else 1.
    settings = [(league, shrink, rho, scale) for league in (0., .5, 1.) for shrink in (.5, 1.)
                for rho in (0., -.08) for scale in sorted({1., trained_scale})]
    scores = {}
    for setting in settings:
        rows = records(valid, setting)
        scores[setting] = mean((row[CANDIDATE][key] - row["labels"][market]) ** 2
                               for row in rows for market, key in KEYS.items())
    selected = min(scores, key=scores.get)
    margin_counts = [sum(f[2] is not None for _, _, f in part) for part in parts]
    result.update(settings=selected, training_total_goal_scale=trained_scale, cross_league_by_split=margin_counts, splits=[len(p) for p in parts],
                  validation_brier={str(k): v for k, v in scores.items()},
                  test=measure(records(test, selected)),
                  test_europe=measure(records([r for r in test if r[1]["competition"] in EUROPE], selected)),
                  test_cross_league=sum(r[2][2] is not None for r in test),
                  test_start=test[0][0].isoformat())
    calibration_setting = (0., .5, 0., trained_scale)
    result["research_calibration"] = calibration_candidates(
        records(train, calibration_setting), records(valid, calibration_setting), records(test, calibration_setting))
    result["research_calibration"]["candidate_settings"] = calibration_setting
    cross_valid = [r for r in valid if r[2][2] is not None]
    cross_test = [r for r in test if r[2][2] is not None]
    if cross_valid and cross_test:
        def margin_loss(scale):
            rows = records(cross_valid, (scale, *selected[1:]))
            return mean((row[CANDIDATE][key] - row["labels"][market]) ** 2
                        for row in rows for market, key in KEYS.items())

        scales = {scale: margin_loss(scale) for scale in (0., .5, 1.)}
        best = min(scales, key=scales.get)
        with_margin = records(cross_test, (best, *selected[1:]))
        without = records(cross_test, (0., *selected[1:]))
        for candidate, control in zip(with_margin, without, strict=True):
            candidate[REFERENCE] = control[CANDIDATE]
        result["league_ablation"] = {"validation_n": len(cross_valid), "test_n": len(cross_test),
                                     "selected_scale": best, "validation_brier": scales,
                                     "reference_scope": "SAME_CANDIDATE_WITHOUT_LEAGUE_COEFFICIENT",
                                     "test": measure(with_margin)}
    history = History()
    for row in sorted(eligible, key=lambda r: (r["finished"], r["kickoff"], r["event_id"])):
        history.update(row)
    ratings, counts = history.league_coefficients()
    result.update(europe_rating_inputs=len(history.europe), league_ratings_goal_units={
        league: {"rating": ratings.get(league) if counts.get(league, 0) >= 3 else None,
                 "appearances": counts.get(league, 0)} for league in DOMESTIC.values()})
    return result


def attach_daily(daily, facts, cutoff, experiment_report):
    if "settings" not in experiment_report:
        return 0
    targets = [{"event_id": row["fixture"]["event_id"], "teams": row["fixture"]["team_ids"],
                "competition": APPROVED_LEAGUES[row["fixture"]["league"]][1],
                "kickoff": utc(row["fixture"]["kickoff_at"]), "as_of": cutoff} for row in daily]
    usable = [r for r in facts if r["captured_at"] < cutoff]
    forecasts = {r["event_id"]: (f, forecast(f, experiment_report["settings"])[1])
                 for r, f in replay(usable, targets)}
    count = 0
    for row in daily:
        result = forecasts.get(row["fixture"]["event_id"])
        reference = (row["domestic_research"] or {}).get("baseline")
        if result and reference:
            (home, away, margin), candidate = result
            row["performance_v1"] = {"status": "RESEARCH_ONLY", "production_allowed": False,
                                     REFERENCE: reference, CANDIDATE: candidate,
                                     "settings": experiment_report["settings"], "league_margin": margin,
                                     "base_quality": {"home": home[2], "away": away[2]},
                                     "adjusted_form": {"home": home[1], "away": away[1]}}
            count += 1
    return count


def settled_daily_pairs(packs, outcomes):
    by_event = {row["event_id"]: row for row in outcomes}
    chosen = {}
    for receipt in packs.glob("*/receipt.json"):
        path = receipt.parent / "forecasts/daily-analysis.json"
        if not path.is_file():
            continue
        sealed = utc(json.loads(receipt.read_bytes())["created_at"])
        for forecast in json.loads(path.read_bytes()):
            pair = forecast.get("performance_v1")
            fixture = forecast["fixture"]
            event = fixture["event_id"]
            outcome = by_event.get(event)
            if (not pair or not outcome or
                    outcome.get("official_review", {}).get("scope") != "REVIEWED_OFFICIAL_RESULT"):
                continue
            kickoff = utc(fixture["kickoff_at"])
            if (fixture["league"] != outcome["league"] or fixture["team_ids"] != outcome["teams"]
                    or kickoff != utc(outcome["kickoff"])
                    or not utc(forecast["as_of"]) <= sealed < kickoff < utc(outcome["settled_at"])):
                continue
            previous = chosen.get(event)
            if previous is None or sealed < previous[0]:
                chosen[event] = sealed, {"date": kickoff.date(), "labels": outcome["labels"],
                                         **{version: pair[version] for version in (REFERENCE, CANDIDATE)}}
            elif sealed == previous[0] and any(previous[1][v] != pair[v] for v in (REFERENCE, CANDIDATE)):
                raise ValueError("Conflicting paired forecasts sealed at the same instant")
    rows = [entry[1] for entry in chosen.values()]
    return {"matched": len(rows), "markets": measure(rows), "production_allowed": False}
