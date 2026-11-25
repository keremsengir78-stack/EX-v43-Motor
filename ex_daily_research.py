"""Keep date-granular domestic UCL baselines outside the frozen holdout ledger."""

import json

from ex_auto_control import auto_control
from ex_cross_verify import norm
from ex_decision import assess_markets
from ex_fixture_odds import check_fixture, check_odds
from ex_history_archive import utc
from ex_leagues import APPROVED_LEAGUES, season_bounds
from ex_ucl_baseline import cross_league_baseline
from run_ucl_baselines import CUTOFF, FIXTURE_CONFIG, captured_rows, select_rows, team_index

MARKET_KEYS = {"2.5_UST": "over25", "KG_VAR": "btts", "MS1": "home_win",
               "MSX": "draw", "MS2": "away_win"}


def domestic_snapshot(root):
    config = json.loads(FIXTURE_CONFIG.read_text())
    leagues, aliases = team_index(config["domestic_team_names"])
    names = {}
    for (_, alias), name in aliases.items():
        if names.setdefault(alias, name) != name:
            raise ValueError(f"Ambiguous domestic team alias: {alias}")
    rows, coverage = select_rows(captured_rows(root), aliases)
    fixtures = {(utc(row["kickoff_at"]), row["home"], row["away"]) for row in config["fixtures"]}
    return rows, coverage, names, leagues, fixtures


DOMESTIC_BY_SLUG = {data[1]: league for league, data in APPROVED_LEAGUES.items() if league != "UCL"}


def rolling_domestic(fixture, by_team, as_of, *, retrospective=False):
    """Join current domestic membership by ESPN club ID; never infer from a name."""
    cutoff = as_of.date()
    rows, leagues = [], []
    for side in ("home", "away"):
        club = fixture["team_ids"][side]
        history = [row for row in by_team.get(club, ())
                   if row["competition"] in DOMESTIC_BY_SLUG and row["kickoff"].date() < cutoff
                   and row["finished"] is not None and row["score"] is not None
                   and (row["finished"] < as_of if retrospective
                        else row["finished"] <= row["captured_at"] < as_of)]
        current = {row["competition"] for row in history
                   if row["kickoff"].date() >= season_bounds(DOMESTIC_BY_SLUG[row["competition"]], cutoff)[0]}
        if len(current) != 1:
            return None
        competition, = current
        league = DOMESTIC_BY_SLUG[competition]
        leagues.append(league)
        rows.extend({"date": row["kickoff"].date(), "league": league,
                     "home": row["teams"]["home"], "away": row["teams"]["away"],
                     "hg": row["score"][0], "ag": row["score"][1]} for row in history
                    if row["competition"] == competition)
    unique = {(r["league"], r["date"], r["home"], r["away"]): r for r in rows}
    first, prior = season_bounds("UCL", cutoff)
    return sorted(unique.values(), key=lambda row: row["date"]), fixture, *leagues, fixture["team_ids"]["home"], fixture["team_ids"]["away"], first.isoformat(), prior.isoformat()


def daily_analysis(fixture, window, snapshot, as_of, *, venue_recomputed=False, by_team=None):
    """Join the two models for display while leaving their evaluation cohorts separate."""
    baseline = None
    recomputed = False
    if fixture["league"] == "UCL" and by_team:
        inputs = rolling_domestic(fixture, by_team, as_of)
        if inputs:
            kwargs = {"cutoff_date": as_of.date().isoformat()}
            baseline = cross_league_baseline(*inputs, **kwargs)
            recomputed = baseline == cross_league_baseline(*inputs, **kwargs)
            baseline["history_scope"] = "ROLLING_DOMESTIC_PROVIDER_TEAM_ID"
    if fixture["league"] == "UCL" and snapshot and not (baseline or {}).get("baseline"):
        rows, _, names, leagues, fixtures = snapshot
        home, away = (names.get(norm(fixture[side])) for side in ("home", "away"))
        kickoff = utc(fixture["kickoff_at"])
        if (kickoff, home, away) in fixtures and utc(CUTOFF + "T00:00:00Z") <= as_of:
            inputs = (rows, fixture, leagues[home], leagues[away], home, away, "2026-07-01", "2025-07-01")
            baseline = cross_league_baseline(*inputs)
            recomputed = baseline == cross_league_baseline(*inputs)
            baseline["history_scope"] = "VERIFIED_MATCHDAY5_DOMESTIC_SNAPSHOT"
    values = baseline.get("baseline") if baseline else None
    if values:
        market_percentages = {market: 100 * values[key] for market, key in MARKET_KEYS.items()}
    elif window is not None:
        market_percentages = {market: 100 * value for market, value in window.items()}
        market_percentages["MSX"] = max(0.0, 100 - market_percentages["MS1"] - market_percentages["MS2"])
        recomputed = venue_recomputed
    else:
        market_percentages = None
    time = as_of.isoformat()
    gate = {"status": "BASELINE_ONLY" if values or window is not None else "INCOMPLETE",
            "fixture_lock": check_fixture(fixture, time), "odds_lock": check_odds(None, time),
            "market_baselines_pct": market_percentages,
            "recompute_consistent": recomputed}
    return {"fixture": fixture, "as_of": time, "venue5_research": window,
            "domestic_research": baseline, "markets": assess_markets({}, as_of=time),
            "tur2": recomputed if market_percentages else None, "auto_control": auto_control(gate),
            "calibration_cohort": "VENUE5_ONLY" if window else None, "ex_final_allowed": False}
