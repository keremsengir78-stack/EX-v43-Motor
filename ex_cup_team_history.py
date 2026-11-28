"""Fetch ID-bound domestic histories for cup opponents missing archive coverage."""

import csv
from datetime import datetime, timedelta
import io
import json

from ex_history_archive import BudgetExhausted, source_error
from ex_history_sources import ESPN, teams
from ex_history_archive import utc
from ex_leagues import APPROVED_LEAGUES, CALENDAR_YEAR_LEAGUES, CUP_HISTORY_SLUGS, UEFA_CUPS, season_bounds
from ex_team_identity import team_identities

DOMESTIC_SLUGS = {key: value[1] for key, value in APPROVED_LEAGUES.items()
                  if key not in UEFA_CUPS} | CUP_HISTORY_SLUGS

# These ESPN IDs are the same IDs published in the cup fixture. A schedule
# must still independently identify that club, league and requested season.
TEAM_LEAGUES = {"20301": "se.1", "256": "sco.1", "262": "sco.1",
                "572": "dk.1", "7853": "dk.1", "3101": "dk.1", "909": "dk.1"}


# Explicit cross-provider bindings reviewed against the UEFA fixture/ESPN ID
# and a matching domestic official result (date, teams, side and score).
CSV_LEAGUES = {
    "ch.1": ("SWZ", "Switzerland", "Super League"),
    "pl.1": ("POL", "Poland", "Ekstraklasa"),
    "fi.1": ("FIN", "Finland", "Veikkausliiga"),
    "ro.1": ("ROU", "Romania", "Superliga"),
}
CSV_CLUBS = {
    "3024": ("ch.1", "Thun", ("21/11/2026", "Young Boys", "Thun", "3", "2"),
             "https://matchcenter-sfl.football.ch/Default.aspx?a=rr&lng=1&oid=2&v=877701"),
    "7672": ("ch.1", "Lugano", ("21/11/2026", "Lugano", "Grasshoppers", "2", "1"),
             "https://matchcenter-sfl.football.ch/Default.aspx?a=rr&lng=1&oid=2&v=877701"),
    "2990": ("pl.1", "Lech Poznan", ("22/11/2026", "GKS Katowice", "Lech Poznan", "0", "1"),
             "https://ekstraklasa.org/mecz/2143d594-ad18-427c-b526-2e43c2fd1ea3/gks-katowice-lech-poznan/przeglad/"),
    "11505": ("pl.1", "Jagiellonia", ("21/11/2026", "Cracovia", "Jagiellonia", "3", "1"),
              "https://ekstraklasa.org/en/match/0ac80736-4d3f-49ed-8dbb-83f761fd833d/cracovia-jagiellonia-bialystok/live/"),
    "8169": ("fi.1", "KuPS", ("08/11/2026", "KuPS", "Inter Turku", "0", "2"),
             "https://www.veikkausliiga.com/joukkueet/kups/otteluohjelma"),
    "8089": ("ro.1", "Univ. Craiova", ("22/11/2026", "UTA Arad", "Univ. Craiova", "2", "6"),
             "https://www.superliga.ro/meci/superliga-26-27-regular-uta-ucv?sectiune=cronica"),
}
TEAM_LEAGUES.update({team: entry[0] for team, entry in CSV_CLUBS.items()})


def csv_facts(raw, stamp, league, day, clubs):
    _, country, competition = CSV_LEAGUES[league]
    slug = DOMESTIC_SLUGS[league]
    aliases = {CSV_CLUBS[club][1]: club for club in clubs}
    seasons = {(str(start.year) if league in CALENDAR_YEAR_LEAGUES else
                f"{start.year}/{start.year+1}"): start.year for start in season_bounds(league, day)}
    anchors = {CSV_CLUBS[club][2] for club in clubs}
    seen, matches = set(), {}
    for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
        year = seasons.get(row["Season"].strip())
        if year is None:
            continue
        if (row["Country"].strip(), row["League"].strip()) != (country, competition):
            continue
        match_day = datetime.strptime(row["Date"], "%d/%m/%Y").date()
        if season_bounds(league, match_day)[0].year != year:
            raise ValueError("Domestic CSV season disagrees with the calendar")
        if match_day >= min(day, stamp.date()):
            continue
        fields = tuple(row[key] for key in ("Date", "Home", "Away", "HG", "AG"))
        if fields in anchors:
            seen.add(fields)
        _, home, away, hg, ag = fields
        if not hg.isdecimal() or not ag.isdecimal() or max(int(hg), int(ag)) > 30:
            continue
        sides = {side: aliases.get(name, f"football-data:{slug}:{name}")
                 for side, name in (("home", home), ("away", away))}
        key = f"football-data:{slug}:{match_day}:{home}:{away}"
        match = {"event_id": key, "teams": sides, "competition": slug, "season": year,
                 "kickoff": utc(f"{match_day}T00:00:00Z"), "score": (int(hg), int(ag)),
                 "finished": stamp, "captured_at": stamp, "date_precision": "DAY",
                 "evidence_scope": "ESPN_SCOREBOARD_RESEARCH"}
        if matches.setdefault(key, match) != match:
            raise ValueError("Conflicting domestic CSV scores")
    if seen != anchors:
        raise ValueError("Reviewed domestic score anchor missing")
    return list(matches.values())


def schedule_facts(raw, stamp, club, league, season):
    payload = json.loads(raw)
    slug = DOMESTIC_SLUGS[league]
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


def reviewed_schedule_plan(day, as_of):
    plan = {club: {start.year: league for start in season_bounds(league, day)}
            for club, league in TEAM_LEAGUES.items()}
    for club, entry in team_identities().items():
        if entry["observed"] >= as_of:
            continue
        for season, league in entry["memberships"].items():
            if season in {start.year for start in season_bounds(league, day)}:
                known = plan.setdefault(club, {}).get(season)
                if known is not None and known != league:
                    raise ValueError("Conflicting domestic source membership")
                plan[club][season] = league
    return plan


def collect_cup_history(archive, manifest):
    clubs = {club for league in UEFA_CUPS
             for fixture in manifest["reports"].get(league, {}).get("records", [])
             for club in fixture["teams"].values()}
    facts, sources, issues = [], [], []
    day = utc(manifest["day"] + "T00:00:00Z").date()
    plan = reviewed_schedule_plan(day, archive.clock())
    for club in sorted((clubs & plan.keys()) - CSV_CLUBS.keys()):
        for season, league in sorted(plan[club].items()):
            url = f"{ESPN}/{DOMESTIC_SLUGS[league]}/teams/{club}/schedule?season={season}"
            try:
                rows, source = archive.get(url, lambda raw, stamp: schedule_facts(raw, stamp, club, league, season),
                                           max_age=timedelta(hours=20))
            except (OSError, ValueError, TypeError, KeyError, AttributeError, BudgetExhausted) as exc:
                issues.append(source_error("cup_domestic_schedule", url, exc))
                continue
            if not rows:
                issues.append({"category": "NO_FINALIZED_SEASON_MATCHES", "url": url, "club": club,
                               "season": season, "league": league})
                continue
            facts.extend(rows)
            sources.append({**source, "club": club, "league": league, "season": season, "matches": len(rows)})
    for league, (file, _, _) in CSV_LEAGUES.items():
        selected = sorted(club for club in clubs if club in CSV_CLUBS and TEAM_LEAGUES[club] == league)
        if not selected:
            continue
        url = f"https://football-data.co.uk/new/{file}.csv"
        try:
            rows, source = archive.get(url, lambda raw, stamp: csv_facts(raw, stamp, league, day, selected),
                                       max_age=timedelta(hours=20))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, BudgetExhausted) as exc:
            issues.append(source_error("cup_domestic_csv", url, exc))
            continue
        facts.extend(rows)
        sources.append({**source, "league": league, "clubs": selected, "matches": len(rows),
                        "identity_evidence": {club: CSV_CLUBS[club][3] for club in selected}})
    return facts, sources, issues
