"""Replay existing UCL inputs and evaluate research models without live collection."""

import argparse
import datetime as dt
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from ex_auto_control import auto_control, snapshot
from ex_cross_verify import norm
from ex_decision import MARKETS, WEIGHTS, assess_market_value, assess_markets
from ex_engine import baseline_backtest_observations, distribution
from ex_espn_provider import parse_espn_scoreboard
from ex_fixture_odds import check_fixture
from ex_model_challengers import compare_calibration
from ex_ucl_baseline import cross_league_baseline
from ex_ucl_strength import compare_league_challengers
from run_ucl_baselines import CUTOFF, FIXTURE_CONFIG, captured_rows, select_rows, team_index, verified_bytes
from run_ucl_matchday_inputs import market_quotes, observed_load, parse_team_news, timestamp
from run_ucl_research import MATCHDAY_DATES, UEFA_SNAPSHOT, espn_fixtures, uefa_fixtures, verify_historical_scores


RUN_AS_OF = "2026-11-24T10:24:34Z"
MARKET_FIELDS = {"2.5_UST": "over25", "KG_VAR": "btts", "MS1": "home_win", "MS2": "away_win", "MSX": "draw"}
BLOCKERS = {
    "team_strength": "Validate the team-strength score for each market in the intended competition.",
    "match_conditions": "Validate a market-specific score from prematch workload and reported material absences, with player minutes where needed. Use verified lineup-independent evidence when a starting XI is unavailable.",
    "external_factors": "Obtain archived travel and venue-effect observations and validate their market effects.",
    "calibration": "Validate frozen weighted-market forecasts on independent chronological outcomes.",
    "source_independence": "Verify independent providers and complete the ingestion/source controls.",
    "pup": "Run the approved PUP protocol after independent markets and mandatory calibration pass.",
}


def raw_snapshot(directory, meta):
    if Path(meta["file"]).name != meta["file"]:
        raise ValueError("Invalid snapshot file name")
    return verified_bytes(directory / meta["file"], meta["sha256"])


def reported_count(value):
    if not value:
        return None
    if value.casefold() == "none":
        return 0
    # Split only top-level commas, preserving qualifiers such as (ankle, foot).
    return len(re.split(r",\s*(?![^()]*\))", value))


def context_measurements(load, preview, kickoff, captured_at):
    times = {}
    for event in load["matches_shown"]:
        when = timestamp(event["kickoff_at"])
        if when >= captured_at or event["event_id"] in times:
            raise ValueError("Recent event invalid or observed after snapshot")
        times[event["event_id"]] = when
    hours = [(kickoff - when).total_seconds() / 3600 for when in times.values()]
    players = [name.strip() for name in re.split("[;,]", preview["predicted_lineup"]) if name.strip()]
    return {
        "shown_completed_matches": len(hours),
        "min_matches_in_last_7_days": sum(0 < h <= 168 for h in hours),
        "min_matches_in_last_14_days": sum(0 < h <= 336 for h in hours),
        "max_hours_since_latest_match": round(min(hours), 2) if hours else None,
        "reported_out_count": reported_count(preview["out"]),
        "reported_doubtful_count": reported_count(preview["doubtful"]),
        "reported_out": preview["out"],
        "reported_doubtful": preview["doubtful"],
        "predicted_lineup_slots": len(players),
        "confirmed_rotation_changes": None,
        "absence_weighted_by_prior_minutes": None,
    }


def score_grid_marginals(home_rate, away_rate):
    """Independently aggregate market probabilities from a recurrent score grid."""
    def probabilities(rate):
        mass = math.exp(-rate)
        values = [mass]
        for goals in range(1, 30):
            mass *= rate / goals
            values.append(mass)
        return values

    grid = [(h, a, p * q) for h, p in enumerate(probabilities(home_rate))
            for a, q in enumerate(probabilities(away_rate))]
    markets = {
        "over25": lambda h, a: h + a >= 3, "btts": lambda h, a: h > 0 and a > 0,
        "home_win": lambda h, a: h > a, "away_win": lambda h, a: h < a,
        "draw": lambda h, a: h == a,
    }
    return {market: math.fsum(p for h, a, p in grid if predicate(h, a))
            for market, predicate in markets.items()}


def replay_fixture(fixture, prematch, baseline, raw_dir, news, aliases, uefa_keys, domestic_dates):
    if prematch["fixture"] != fixture or baseline["fixture"] != fixture:
        raise ValueError("Fixture identity mismatch")
    cutoff, kickoff = timestamp(RUN_AS_OF), timestamp(fixture["kickoff_at"])
    matchup = kickoff, norm(fixture["home"]), norm(fixture["away"])
    board_meta, summary_meta = prematch["scoreboard_source"], prematch["summary_source"]
    if not all(timestamp(src["retrieved_at"]) < cutoff < kickoff for src in (board_meta, summary_meta)):
        raise ValueError("Fixture data captured outside the prematch window")
    board = raw_snapshot(raw_dir, board_meta)
    summary = json.loads(raw_snapshot(raw_dir, summary_meta))
    matches = list(zip(json.loads(board)["events"], espn_fixtures(board, aliases), strict=True))
    (event, _), = [(event, key) for event, key in matches if key == matchup]
    header = summary["header"]
    competition, = header["competitions"]
    if (header["id"] != event["id"] or timestamp(competition["date"]) != kickoff
            or competition["status"]["type"]["state"] != "pre" or event["status"]["type"]["state"] != "pre"):
        raise ValueError("Snapshot identity or prematch status mismatch")
    (board_competition,) = event["competitions"]
    ids = {side["homeAway"]: side["id"] for side in competition["competitors"]}
    if ids != {side["homeAway"]: side["id"] for side in board_competition["competitors"]}:
        raise ValueError("Summary team identity mismatch")
    captured_at = timestamp(summary_meta["retrieved_at"])
    actual_load = observed_load(summary, set(ids.values()), captured_at, kickoff)
    preview = news[matchup[1:]]
    if preview != prematch["uefa_preview"]:
        raise ValueError("Team news snapshot mismatch")
    measurements = {
        side: context_measurements(actual_load[team], preview[side], kickoff, captured_at)
        for side, team in ids.items()
    }
    for side, result in measurements.items():
        dates = domestic_dates[baseline["domestic_leagues"][side], fixture[side]]
        day = kickoff.date()
        prior = [played for played in dates if played < day]
        result["latest_domestic_result_date"] = max(prior).isoformat() if prior else None
        result["domestic_results_in_prior_14_calendar_days"] = sum(
            (day - played).days <= 14 for played in prior
        )
    quotes = market_quotes(board_competition.get("odds", []), board_meta, fixture["kickoff_at"])
    booked, recorded = defaultdict(list), defaultdict(list)
    for quote in quotes:
        booked[quote["market"]].append(quote)
    for quote in prematch.get("market_quotes") or []:
        recorded[quote["market"]].append(quote)
    archived = baseline["baseline"]
    scores = distribution(archived["lambda_home"], archived["lambda_away"])
    if not math.isclose(sum(scores[k] for k in ("home_win", "draw", "away_win")), 1, abs_tol=1e-9):
        raise ValueError("Score distribution probabilities do not sum to one")
    independent_grid = score_grid_marginals(scores["lambda_home"], scores["lambda_away"])
    max_delta = max(abs(scores[market] - value) for market, value in independent_grid.items())
    consistent = (max_delta < 1e-9 and snapshot(scores) == snapshot(archived)
                  and {side: actual_load[team] for side, team in ids.items()} == prematch["observed_match_load"])
    fixture_lock = check_fixture({
        **fixture, "fixture_source": board_meta["url"], "fixture_checked_at": board_meta["retrieved_at"],
    }, RUN_AS_OF) if matchup in uefa_keys else {"status": "BLOCKED"}
    # The underlying observations are available, but lack validated score mappings.
    weighted = assess_markets({}, as_of=RUN_AS_OF)
    venue = board_competition.get("venue")
    neutral_site = competition.get("neutralSite")
    context_inputs = {
        "match_conditions": {"status": "OBSERVATIONS_AVAILABLE_SCORE_MISSING",
                             "measurements": ["observed_workload", "reported_absences"],
                             "confirmed_lineup_required": False},
        "external_factors": {"status": "OBSERVATIONS_AVAILABLE_SCORE_MISSING",
                             "venue": venue, "neutral_site": neutral_site},
    }
    markets = {}
    for market in MARKETS:
        offers = booked[market]
        quote_consistent = offers == recorded[market]
        quote = offers[0] if quote_consistent and len(offers) == 1 else None
        evidence = weighted["markets"][market]
        ex_g = evidence["ex_g"]
        value = assess_market_value(market, ex_g, quote, RUN_AS_OF)
        if not quote_consistent:
            value["odds_lock"]["issues"] = ["odds:replay_mismatch"]
        p = scores[MARKET_FIELDS[market]]
        markets[market] = {
            "baseline": {"status": "AVAILABLE", "probability": archived[MARKET_FIELDS[market]]},
            "research_probability": {"status": "UNCALIBRATED", "probability": p},
            "team_strength_research_probability": p,
            "research_weighted_team_strength_contribution": WEIGHTS["team_strength"] * p,
            "weighted_evidence": evidence,
            "ex_g_status": ex_g["status"], "ex_g_issues": ex_g["issues"],
            "ex_g": ex_g["probability"], "quote_replay_consistent": quote_consistent,
            **value,
        }
    percent = {m: round(100 * scores[k], 2) for m, k in MARKET_FIELDS.items()}
    gate_input = {
        "fixture": fixture, "status": "BASELINE_ONLY", "recompute_consistent": consistent,
        "fixture_lock": fixture_lock, "market_baselines_pct": percent,
    }
    for record in markets.values():
        control = auto_control({**gate_input, "odds_lock": record["odds_lock"]})
        record["auto_control"] = control
        record["final"] = {"status": "NO_FINAL", "issues": control["issues"], "ex_final_allowed": False}
    return {
        "fixture": fixture, "decision": "NO_FINAL", "fixture_lock": fixture_lock,
        "scoreboard_source": board_meta, "summary_source": summary_meta,
        "uefa_match_id": preview["uefa_match_id"],
        "measurements": measurements, "context_inputs": context_inputs, "venue": venue,
        "neutral_site": neutral_site, "score_distribution": scores,
        "markets": markets, "tur2_recompute_consistent": consistent,
        "tur2_score_grid_max_absolute_delta": max_delta,
        "pup_allowed": False, "ex_final_allowed": False,
    }


def add_calibration_record(data, day, baseline, hg, ag, home_dates, away_dates):
    recent = [[(day - d).days for d in dates if d < day] for dates in (home_dates, away_dates)]
    if not all(recent):
        return
    home, away = recent
    # Fixed scales keep the two dimensions comparable during regularization.
    rest_gap = (min(14, min(home)) - min(14, min(away))) / 14
    load_gap = (sum(d <= 14 for d in home) - sum(d <= 14 for d in away)) / 4
    actual = {"2.5_UST": hg + ag >= 3, "KG_VAR": hg > 0 and ag > 0, "MS1": hg > ag, "MS2": hg < ag}
    for market in MARKETS:
        data[market].append((day, baseline[MARKET_FIELDS[market]], actual[market], (rest_gap, load_gap)))


def calibrate_domestic(rows, schedules, historical_ucl, config, aliases):
    data = {market: [] for market in MARKETS}
    for row, baseline in baseline_backtest_observations(rows):
        add_calibration_record(data, row["date"], baseline, row["hg"], row["ag"],
                               schedules[row["league"], row["home"]], schedules[row["league"], row["away"]])
    external = {market: [] for market in MARKETS}
    leagues, _ = team_index(config["domestic_team_names"])
    names = {norm(team): team for team in leagues}
    for match in historical_ucl:
        home, away = (names[aliases[norm(match[side])]] for side in ("home", "away"))
        fixture = {"date": match["date"], "home": home, "away": away}
        result = cross_league_baseline(rows, fixture, leagues[home], leagues[away],
                                       home, away, "2026-07-01", "2025-07-01", cutoff_date=match["date"])
        if "baseline" in result:
            add_calibration_record(
                external, dt.date.fromisoformat(match["date"]), result["baseline"],
                match["home_goals"], match["away_goals"], schedules[leagues[home], home], schedules[leagues[away], away],
            )
    return {market: compare_calibration(data[market], external[market]) for market in MARKETS}


def league_replay(archive, config, uefa, aliases):
    historical = json.loads((archive / "report.json").read_text())
    rows = []
    for meta in historical["requests"]:
        raw = verified_bytes(archive / "raw" / (meta["sha256"] + ".json"), meta["sha256"])
        rows.extend(parse_espn_scoreboard(json.loads(raw), "UCL", CUTOFF, meta["date"]))
    checks = verify_historical_scores(uefa, rows, aliases, 5)
    if checks["exact_score_agreements"] != 72 or len(rows) != 72:
        raise ValueError("Historical UEFA–ESPN league sample mismatch")
    leagues, _ = team_index(config["domestic_team_names"])
    lookup = {norm(team): league for team, league in leagues.items()}
    rounds = [[(lookup[aliases[norm(r["home"])]], lookup[aliases[norm(r["away"])]],
                r["home_goals"] - r["away_goals"]) for r in rows if r["date"] in dates]
              for dates in MATCHDAY_DATES[:4]]
    if any(len(round_rows) != 18 for round_rows in rounds):
        raise ValueError("League matches cannot be split into four complete matchdays")
    return rows, compare_league_challengers(rounds[0] + rounds[1], rounds[2], rounds[3])


def run(archive, *, experiments=False):
    config = json.loads(FIXTURE_CONFIG.read_text())
    prematch = json.loads(Path("reports/ucl_matchday5_prematch_2026_11_24.json").read_text())
    baselines = json.loads((archive / "archive_baselines.json").read_text())
    aliases = {norm(variant): norm(team) for clubs in config["domestic_team_names"].values()
               for team, variants in clubs.items() for variant in [team, *variants]}
    raw_dir = archive / "matchday_inputs"
    news_meta = prematch["uefa_preview_source"]
    uefa_meta = json.loads(UEFA_SNAPSHOT.with_suffix(".json").read_text())
    if max(timestamp(src["retrieved_at"]) for src in (news_meta, uefa_meta)) >= timestamp(RUN_AS_OF):
        raise ValueError("UEFA information was not available at evaluation time")
    news = parse_team_news(raw_snapshot(raw_dir, news_meta))
    uefa = verified_bytes(UEFA_SNAPSHOT.with_suffix(".html"), uefa_meta["sha256"])
    verified_fixtures = set(uefa_fixtures(uefa, 5))

    def index(items):
        return {(r["fixture"]["home"], r["fixture"]["away"]): r for r in items}

    base, observations = index(baselines), index(prematch["fixtures"])
    _, domestic_aliases = team_index(config["domestic_team_names"])
    rows, _ = select_rows(captured_rows(archive), domestic_aliases)
    schedules = defaultdict(list)
    for row in rows:
        for side in ("home", "away"):
            schedules[row["league"], row[side]].append(row["date"])
    today = [fixture for fixture in config["fixtures"] if fixture["date"] == CUTOFF]
    results = [replay_fixture(f, observations[f["home"], f["away"]], base[f["home"], f["away"]],
                              raw_dir, news, aliases, verified_fixtures, schedules) for f in today]
    if len(results) != 9 or any(not row["tur2_recompute_consistent"] for row in results):
        raise ValueError("Incomplete or inconsistent Tur-2 replay for today's fixtures")
    report = {
        "as_of": RUN_AS_OF, "fixtures": results, "uefa_preview_source": news_meta,
        "blocker_resolutions": {**BLOCKERS, "verified_market_quote": "Capture a bookmaker quote for the exact market before kickoff."},
        "pup_allowed": False, "ex_final_allowed": False,
    }
    if experiments:
        historical_ucl, leagues_report = league_replay(archive, config, uefa, aliases)
        report["historical_calibration"] = calibrate_domestic(rows, schedules, historical_ucl, config, aliases)
        report["ucl_league_challengers"] = leagues_report
        report["calibration_scope"] = "Retrospective domestic forecasts; workload proxies are domestic-only, date-granular."
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("ucl_research_output"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--experiments", action="store_true", help="Rerun historical experiments explicitly")
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.archive, experiments=args.experiments), ensure_ascii=False, indent=2) + "\n")
