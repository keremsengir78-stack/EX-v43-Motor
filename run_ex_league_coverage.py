"""Compare the league capabilities registered in EX without changing activation."""

import json
from pathlib import Path

from ex_espn_provider import ESPN_LEAGUES
from ex_live_data import LEAGUES
from run_ex_official_minutes_batch import OFFICIAL_HOSTS
from run_ex_official_sources import ALTERNATE_CALENDARS
from run_ex_prospective_pipeline import OFFICIAL_RESULT_HOSTS

# Explicitly identified in the user-approved scope for this review.
APPROVED_SCOPE_GAPS = {"nl.2": "Netherlands Eerste Divisie"}


def coverage(config):
    history = config["leagues"]
    rows = {}
    for league in sorted(set().union(LEAGUES, ESPN_LEAGUES, history, APPROVED_SCOPE_GAPS)):
        league_config = history.get(league, {})
        seasons = sorted({team["season"] for team in league_config.get("teams", [])})
        rows[league] = {
            "league_name": LEAGUES.get(league, APPROVED_SCOPE_GAPS.get(league)),
            "main_ingestion": league in LEAGUES,
            "espn_adapter": ESPN_LEAGUES.get(league),
            "history_seed_seasons": seasons,
            "history_seed_competition_consistent": (league_config["espn_competition"] == ESPN_LEAGUES.get(league)
                                                    if "espn_competition" in league_config else None),
            "alternate_calendar": league in ALTERNATE_CALENDARS,
            "official_minutes_host_registered": league in OFFICIAL_HOSTS,
            "official_result_hosts": sorted(OFFICIAL_RESULT_HOSTS.get(league, ())),
        }
    return {"registered_leagues": rows, "approved_scope_gaps": APPROVED_SCOPE_GAPS,
            "history_seed_seasons_scope": "EXPANSION_CONFIG_ONLY", "ex_final_allowed": False}


if __name__ == "__main__":
    print(json.dumps(coverage(json.loads(Path("config/ex_history_expansion.json").read_text())), indent=2))
