"""Fetch ID-bound domestic histories for cup opponents missing archive coverage."""

from datetime import timedelta
import json

from ex_history_archive import BudgetExhausted, source_error
from ex_history_sources import ESPN, teams
from ex_history_archive import utc
from ex_leagues import CUP_HISTORY_SLUGS, season_bounds

# These ESPN IDs are the same IDs published in the cup fixture. A schedule
# must still independently identify that club, league and requested season.
TEAM_LEAGUES = {"20301": "se.1", "256": "sco.1", "262": "sco.1",
                "572": "dk.1", "7853": "dk.1", "3101": "dk.1", "909": "dk.1"}


def schedule_facts(raw, stamp, club, league, season):
    payload = json.loads(raw)
    slug = CUP_HISTORY_SLUGS[league]
    if payload["team"]["id"] != club or payload["requestedSeason"]["year"] != season:
        raise ValueError("Domestic schedule team or season mismatch")
    matches = {}
    for event in payload["events"]:
        if event["league"]["slug"] != slug or event["season"]["year"] != season:
            raise ValueError("Domestic schedule competition or season mismatch")
        match, = event["competitions"]
        kickoff = utc(event["date"])
        sides = teams(match)
        if match["id"] != event["id"] or utc(match["date"]) != kickoff or club not in sides.values():
            raise ValueError("Domestic schedule fixture identity mismatch")
        status = match["status"]["type"]
        if (status.get("completed") is not True or status.get("name") != "STATUS_FULL_TIME"
                or kickoff + timedelta(minutes=90) > stamp):
            continue
        scores = {side["homeAway"]: side["score"]["value"] for side in match["competitors"]}
        values = scores["home"], scores["away"]
        if any(type(value) not in (int, float) or not 0 <= value <= 30 or value != int(value)
               for value in values):
            raise ValueError("Invalid domestic schedule score")
        row = {"event_id": event["id"], "teams": sides, "competition": slug, "season": season,
               "kickoff": kickoff, "score": tuple(map(int, values)), "finished": stamp,
               "captured_at": stamp, "evidence_scope": "ESPN_SCOREBOARD_RESEARCH"}
        if matches.setdefault(row["event_id"], row) != row:
            raise ValueError("Conflicting fixtures in domestic schedule")
    return list(matches.values())


def collect_cup_history(archive, manifest):
    clubs = {club for league in ("UEL", "UECL")
             for fixture in manifest["reports"].get(league, {}).get("records", [])
             for club in fixture["teams"].values() if club in TEAM_LEAGUES}
    facts, sources, issues = [], [], []
    day = utc(manifest["day"] + "T00:00:00Z").date()
    for club in sorted(clubs):
        league = TEAM_LEAGUES[club]
        for start in season_bounds(league, day):
            url = f"{ESPN}/{CUP_HISTORY_SLUGS[league]}/teams/{club}/schedule?season={start.year}"
            try:
                rows, source = archive.get(url, lambda raw, stamp: schedule_facts(raw, stamp, club, league, start.year),
                                           max_age=timedelta(hours=20))
            except (OSError, ValueError, TypeError, KeyError, AttributeError, BudgetExhausted) as exc:
                issues.append(source_error("cup_domestic_schedule", url, exc))
                continue
            facts.extend(rows)
            sources.append({**source, "club": club, "league": league, "season": start.year, "matches": len(rows)})
    return facts, sources, issues
