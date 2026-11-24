"""ESPN schedules and match facts, plus date-bounded UEFA preview evidence."""

import datetime as dt
import json
import re
from collections import Counter

from ex_history_archive import utc
from ex_uefa_provider import parse_team_news

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer"


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,15}", value):
        raise ValueError("Invalid provider identifier")
    return value


def league_slug(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9._-]{1,60}", value):
        raise ValueError("Invalid competition slug")
    return value


def teams(competition):
    sides = [(row["homeAway"], identifier(row["team"]["id"])) for row in competition["competitors"]]
    mapping = dict(sides)
    if len(sides) != 2 or set(mapping) != {"home", "away"} or len(set(mapping.values())) != 2:
        raise ValueError("Invalid fixture team identities")
    return mapping


def schedule(raw, team_id, season):
    payload = json.loads(raw)
    if (identifier(payload["team"]["id"]) != team_id
            or payload["requestedSeason"]["year"] != season):
        raise ValueError("Schedule team or season mismatch")
    events = {}
    for event in payload["events"]:
        competition, = event["competitions"]
        event_id = identifier(event["id"])
        sides = teams(competition)
        if team_id not in sides.values() or event_id in events or competition["id"] != event_id:
            raise ValueError("Foreign or duplicate schedule event")
        kickoff = utc(event["date"])
        if utc(competition["date"]) != kickoff:
            raise ValueError("Schedule kickoff mismatch")
        state = competition["status"]["type"]
        events[event_id] = {
            "event_id": event_id, "kickoff_at": kickoff.isoformat(),
            "competition": league_slug(event["league"]["slug"]), "teams": sides,
            "source_season": event.get("season", {}).get("year"),
            "completed": state.get("completed") is True and state.get("state") == "post",
        }
    return events


def explicit_minutes(player):
    values = [stat["value"] for stat in player.get("stats", []) if stat.get("name") == "minutesPlayed"]
    if len(values) == 1 and type(values[0]) in (int, float) and 0 <= values[0] <= 130:
        return values[0]
    return None


def regulation_minutes(player):
    """Use ESPN-clock nominal minutes for finished 90-minute matches only."""
    starter, entered, exited = (player.get(key) for key in ("starter", "subbedIn", "subbedOut"))
    if any(type(flag) is not bool for flag in (starter, entered, exited)) or starter and entered:
        return None
    # Dismissals cannot be treated as a full match or as a substitution.
    reds = [stat["value"] for stat in player.get("stats", []) if stat.get("name") == "redCards"]
    if reds != [0] or any(play.get("redCard") for play in player.get("plays", [])):
        return None
    if not starter and not entered:
        return 0 if not exited else None
    clocks = []
    for play in player.get("plays", []):
        if play.get("substitution") is True:
            minute = re.fullmatch(r"(\d{1,2})'(?:\+\d{1,2}')?", play["clock"]["displayValue"])
            if not minute:
                return None
            clocks.append(min(90, int(minute[1])))
    if len(clocks) != int(entered) + int(exited):
        return None
    clocks.sort()
    first = clocks[0] if entered else 0
    last = clocks[-1] if exited else 90
    return last - first


def match_detail(raw, captured, event):
    payload = json.loads(raw)
    header = payload["header"]
    competition, = header["competitions"]
    kickoff = utc(event["kickoff_at"])
    if (header["id"] != event["event_id"] or competition["id"] != event["event_id"]
            or utc(competition["date"]) != kickoff or teams(competition) != event["teams"]):
        raise ValueError("Summary identity differs from schedule")
    state = competition["status"]["type"]
    completed = state.get("state") == "post" and state.get("completed") is True
    game_info = payload.get("gameInfo", {})
    venue = game_info.get("venue")
    # Post-match details cannot be silently repurposed as target pre-match inputs.
    phase = "AFTER_KICKOFF" if captured >= kickoff else "PREMATCH_CAPTURE"
    if completed and phase == "PREMATCH_CAPTURE":
        raise ValueError("Completed summary captured before fixture kickoff")
    roster = []
    roster_teams = set()
    if completed and phase == "AFTER_KICKOFF":
        for block in payload.get("rosters", []):
            team = identifier(block["team"]["id"])
            if event["teams"].get(block["homeAway"]) != team or team in roster_teams:
                raise ValueError("Summary roster team mismatch")
            roster_teams.add(team)
            for player in block.get("roster", []):
                athlete = identifier(player["athlete"]["id"])
                exact = explicit_minutes(player)
                derived = (regulation_minutes(player) if exact is None
                           and state.get("name") == "STATUS_FULL_TIME" else None)
                roster.append({"team_id": team, "athlete_id": athlete,
                               "starter": player.get("starter"), "provider_minutes": exact,
                               "nominal_regulation_minutes": derived})
    player_counts = Counter(player["athlete_id"] for player in roster)
    identity_conflicts = sorted(athlete for athlete, count in player_counts.items() if count > 1)
    roster = [player for player in roster if player_counts[player["athlete_id"]] == 1]
    conflicted_teams = []
    for team in roster_teams:
        player_rows = [player for player in roster if player["team_id"] == team]
        minutes = [player["nominal_regulation_minutes"] for player in player_rows]
        if any(value is not None for value in minutes):
            total = sum(value for value in minutes if value is not None)
            if total > 990 or all(value is not None for value in minutes) and total != 990:
                conflicted_teams.append(team)
                for player in player_rows:
                    player["nominal_regulation_minutes"] = None
    return {"event_id": event["event_id"], "kickoff_at": event["kickoff_at"], "teams": event["teams"], "capture_phase": phase, "completed": completed,
            "venue": venue, "neutral_site": competition.get("neutralSite"), "player_rows": roster,
            "reported_weather": game_info.get("weather"), "travel": None,
            "nominal_minutes_conflict_teams": sorted(conflicted_teams),
            "roster_identity_conflicts": identity_conflicts}


def uefa_news(raw, captured, targets):
    news = {entry["uefa_match_id"]: (clubs, entry) for clubs, entry in parse_team_news(raw).items()}
    output = []
    for target in targets:
        match_id = identifier(target["uefa_match_id"])
        if match_id not in news:
            raise ValueError("UEFA article missing configured match ID")
        clubs, report = news[match_id]
        if list(clubs) != target["normalized_teams"]:
            raise ValueError("UEFA preview team identities differ from configured fixture")
        kickoff = utc(target["kickoff_at"])
        eligible = captured < kickoff
        output.append({"uefa_match_id": match_id, "kickoff_at": kickoff.isoformat(),
                       "prematch_eligible": eligible, "reported_availability": report if eligible else None})
    return output
