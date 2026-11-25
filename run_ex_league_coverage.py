"""Compare the league capabilities registered in EX without changing activation."""

import json
from pathlib import Path

from ex_espn_provider import ESPN_LEAGUES
from ex_live_data import LEAGUES
from ex_leagues import APPROVED_LEAGUES
from ex_cross_verify import DIVISIONS
from run_ex_official_minutes_batch import OFFICIAL_HOSTS
from run_ex_official_sources import ALTERNATE_CALENDARS
from run_ex_prospective_pipeline import OFFICIAL_RESULT_HOSTS

def coverage(config):
    history = config["leagues"]
    rows = {}
    for league in sorted(set().union(LEAGUES, ESPN_LEAGUES, history, APPROVED_LEAGUES)):
        league_config = history.get(league, {})
        seasons = sorted({team["season"] for team in league_config.get("teams", [])})
        approved = APPROVED_LEAGUES.get(league)
        rows[league] = {
            "league_name": LEAGUES.get(league),
            "approved_main_catalog": approved is not None,
            "season_boundary_month": approved[2] if approved else None,
            "historical_score_provider": approved[3] if approved else None,
            "calendar_and_odds_adapter": ESPN_LEAGUES.get(league),
            "secondary_score_adapter": DIVISIONS.get(league),
            "baseline_engine": league in LEAGUES,
            "main_ingestion": league in LEAGUES,
            "espn_adapter": ESPN_LEAGUES.get(league),
            "history_seed_seasons": seasons,
            "history_seed_competition_consistent": (league_config["espn_competition"] == ESPN_LEAGUES.get(league)
                                                    if "espn_competition" in league_config else None),
            "alternate_calendar": league in ALTERNATE_CALENDARS,
            "official_minutes_host_registered": league in OFFICIAL_HOSTS,
            "official_result_hosts": sorted(OFFICIAL_RESULT_HOSTS.get(league, ())),
        }
    return {"registered_leagues": rows, "approved_scope_gaps": sorted(set(APPROVED_LEAGUES) - set(LEAGUES)),
            "history_seed_seasons_scope": "EXPANSION_CONFIG_ONLY", "ex_final_allowed": False}


if __name__ == "__main__":
    print(json.dumps(coverage(json.loads(Path("config/ex_history_expansion.json").read_text())), indent=2))
