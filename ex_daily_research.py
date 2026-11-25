"""Keep date-granular domestic UCL baselines outside the frozen holdout ledger."""

import json

from ex_auto_control import auto_control
from ex_cross_verify import norm
from ex_decision import assess_markets
from ex_fixture_odds import check_fixture, check_odds
from ex_history_archive import utc
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


def daily_analysis(fixture, window, snapshot, as_of):
    """Join the two models for display while leaving their evaluation cohorts separate."""
    baseline = None
    recomputed = False
    if fixture["league"] == "UCL" and snapshot:
        rows, _, names, leagues, fixtures = snapshot
        home, away = (names.get(norm(fixture[side])) for side in ("home", "away"))
        kickoff = utc(fixture["kickoff_at"])
        if (kickoff, home, away) in fixtures and utc(CUTOFF + "T00:00:00Z") <= as_of:
            inputs = (rows, fixture, leagues[home], leagues[away], home, away, "2026-07-01", "2025-07-01")
            baseline = cross_league_baseline(*inputs)
            recomputed = baseline == cross_league_baseline(*inputs)
    values = baseline.get("baseline") if baseline else None
    time = as_of.isoformat()
    gate = {"status": "BASELINE_ONLY" if values or window is not None else "INCOMPLETE",
            "fixture_lock": check_fixture(fixture, time), "odds_lock": check_odds(None, time),
            "market_baselines_pct": {m: 100 * values[k] for m, k in MARKET_KEYS.items()} if values else None,
            "recompute_consistent": recomputed}
    return {"fixture": fixture, "as_of": time, "venue5_research": window,
            "domestic_research": baseline, "markets": assess_markets({}, as_of=time),
            "tur2": recomputed if baseline else None, "auto_control": auto_control(gate),
            "calibration_cohort": "VENUE5_ONLY" if window else None, "ex_final_allowed": False}
