"""Evaluate new component features on frozen domestic and historical UCL archives."""

import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path

from ex_component_experiment import component_vectors, evaluate_components
from ex_cross_verify import norm
from ex_decision import MARKETS, WEIGHTS
from ex_engine import baseline_backtest_observations
from ex_historical_features import HistoricalFeatures, market_labels
from ex_ucl_baseline import cross_league_baseline
from run_ucl_baselines import CUTOFF, FIXTURE_CONFIG, captured_rows, select_rows, team_index, verified_bytes
from run_ucl_model_integration import MARKET_FIELDS, verified_ucl_history
from run_ucl_research import UEFA_SNAPSHOT


def run(archive):
    config = json.loads(FIXTURE_CONFIG.read_text())
    leagues, domestic_aliases = team_index(config["domestic_team_names"])
    rows, _ = select_rows(captured_rows(archive), domestic_aliases)
    features = HistoricalFeatures(rows)
    data = {market: [] for market in MARKETS}
    transfer = {market: [] for market in MARKETS}
    coverage = Counter()

    def append(target, day, baseline, actual, snapshot):
        for market in MARKETS:
            vector = component_vectors(snapshot, market)
            if vector is not None:
                target[market].append((day, baseline[MARKET_FIELDS[market]], actual[market], vector))

    for row in rows:
        league, day = row["league"], row["date"]
        snapshot = features.fixture(league, league, row["home"], row["away"], day)
        if component_vectors(snapshot, "MS1") is not None:
            coverage["two_venue_windows"] += 1
        if all(snapshot[side]["last_domestic_result"] for side in ("home", "away")):
            coverage["two_domestic_rest_observations"] += 1
    for row, baseline in baseline_backtest_observations(rows):
        league, day = row["league"], row["date"]
        append(data, day, baseline, market_labels(row["hg"], row["ag"]),
               features.fixture(league, league, row["home"], row["away"], day))

    aliases = {key: norm(name) for (_, key), name in domestic_aliases.items()}
    names = {norm(team): team for team in leagues}
    uefa_meta = json.loads(UEFA_SNAPSHOT.with_suffix(".json").read_text())
    uefa = verified_bytes(UEFA_SNAPSHOT.with_suffix(".html"), uefa_meta["sha256"])
    for match in verified_ucl_history(archive, uefa, aliases):
        home, away = (names[aliases[norm(match[side])]] for side in ("home", "away"))
        day = dt.date.fromisoformat(match["date"])
        baseline = cross_league_baseline(rows, {"date": match["date"], "home": home, "away": away},
                                        leagues[home], leagues[away], home, away,
                                        "2026-07-01", "2025-07-01", cutoff_date=match["date"])
        if "baseline" in baseline:
            append(transfer, day, baseline["baseline"], market_labels(match["home_goals"], match["away_goals"]),
                   features.fixture(leagues[home], leagues[away], home, away, day))
    return {
        "as_of": CUTOFF, "archive_rows": len(rows), "feature_coverage": dict(coverage), "weights": WEIGHTS,
        "markets": {market: evaluate_components(data[market], transfer[market]) for market in MARKETS},
        "matchday_observations": [
            {"fixture": fixture, **features.fixture(
                leagues[fixture["home"]], leagues[fixture["away"]], fixture["home"], fixture["away"],
                dt.date.fromisoformat(CUTOFF),
            )}
            for fixture in config["fixtures"]
        ],
        "external_factors": {"status": "INSUFFICIENT_HISTORICAL_EVIDENCE",
                             "missing": ["verified travel", "weather impacts", "venue changes", "timestamped availability"]},
        "conditions_scope": "Date-only domestic workload proxy. Full competitive schedules and player minutes are unavailable.",
        "test_scope": "Retrospective temporal holdout and UCL domain check. Historical data publication times are incomplete.",
        "production_allowed": False, "pup_allowed": False, "ex_final_allowed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=Path("ucl_research_output"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args.archive), ensure_ascii=False, indent=2) + "\n")
