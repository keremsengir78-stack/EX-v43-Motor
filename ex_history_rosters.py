"""Season participant evidence from explicit ESPN standings responses."""

import json

from ex_history_archive import BudgetExhausted, source_error
from ex_history_sources import identifier, league_slug


def standing_teams(raw, expected_uid, year):
    data = json.loads(raw)
    if data["season"]["year"] != year or data["uid"] != expected_uid:
        raise ValueError("Standings competition or season mismatch")
    rows = [entry for group in data["children"] for entry in group["standings"]["entries"]]
    teams = sorted({identifier(row["team"]["id"]) for row in rows}, key=int)
    if len(teams) < 8:
        raise ValueError("Insufficient standings participant evidence")
    return teams


def expand_rosters(leagues, seasons, archive):
    roster, errors = [], []
    for league, config in leagues.items():
        competition = league_slug(config["espn_competition"])
        expected_uid = config.get("standings_uid")
        for season in seasons:
            url = f"https://site.api.espn.com/apis/v2/sports/soccer/{competition}/standings?season={season}"
            observed = {item["espn_team_id"] for item in config["teams"] if item["season"] == season}
            if not expected_uid:
                roster.append({"league": league, "season": season, "status": "NO_VALIDATED_STANDINGS_ADAPTER",
                               "observed_seed_count": len(observed)})
                continue
            try:
                teams, source = archive.get(
                    url, lambda raw, _: standing_teams(raw, expected_uid, season),
                    content_schema="espn-standing-v1",
                )
            except BudgetExhausted:
                roster.append({"league": league, "season": season, "status": "DEFERRED"})
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                errors.append(source_error("standings", url, exc))
                roster.append({"league": league, "season": season, "status": "UNVERIFIED",
                               "observed_seed_count": len(observed)})
            else:
                roster.append({"league": league, "season": season, "status": "PROVIDER_STANDINGS_OBSERVED",
                               "observed_seed_count": len(observed), "participant_count": len(teams),
                               "missing_seed_ids": sorted(set(teams) - observed, key=int),
                               "additional_seed_ids": sorted(observed - set(teams), key=int),
                               "team_ids": teams, "source": source})
    return roster, errors
