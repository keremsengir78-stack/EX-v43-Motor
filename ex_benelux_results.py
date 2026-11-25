"""Parse official Belgian and Portuguese match pages with explicit final status."""

import json
import re
from urllib.parse import urlsplit

from ex_history_archive import utc

BELGIUM_CALENDAR = "https://www.proleague.be/jpl-kalender?activeTab=results"
BELGIUM_SAMPLE = "https://www.proleague.be/wedstrijden/seizoen-2026-2027-jupiler-pro-league-12-sporting-charleroi-vs-stvv-702"
PORTUGAL_SAMPLE = "https://www.ligaportugal.pt/match/20262027/ligaportugalbetclic/11/9?tab=match_timeline"


def embedded(raw, marker):
    token = re.search(rb'<script[^>]*id="' + marker + rb'"[^>]*>(.*?)</script>', raw, re.S)
    if not token:
        raise ValueError("Official page has no expected embedded dataset")
    return json.loads(token[1])


def belgian_matches(data):
    pending = [data]
    while pending:
        item = pending.pop()
        if isinstance(item, list):
            pending.extend(item)
        elif isinstance(item, dict):
            if {"homeTeam", "awayTeam", "competition", "period", "time", "slug"} <= item.keys():
                if item["competition"].get("name") == "Jupiler Pro League":
                    yield item
            else:
                pending.extend(item.values())


def belgian_results(raw, url, stamp):
    slug = urlsplit(url).path.rsplit("/", 1)[-1]
    rows = {}
    for item in belgian_matches(embedded(raw, b"__NEXT_DATA__")):
        if item["slug"] != slug or item["period"]["type"] not in {"PostMatch", "FullTime", "MatchFinished", "Finished"}:
            continue
        kickoff = utc(item["time"])
        scores = [item["homeScore"], item["awayScore"]]
        if kickoff >= stamp or any(type(goal) is not int or not 0 <= goal <= 30 for goal in scores):
            continue
        result = {"date": kickoff.date().isoformat(), "home": item["homeTeam"]["name"], "away": item["awayTeam"]["name"],
                  "official_score": scores, "source": url, "source_match_id": item["id"]}
        old = rows.setdefault(item["id"], result)
        if old != result:
            raise ValueError("Conflicting official Belgian score")
    return list(rows.values())


def portuguese_results(raw, url, stamp):
    values = embedded(raw, b"__NUXT_DATA__")
    # Only the match headline has matchDate as well as the final score.
    headers = [row for row in values if isinstance(row, dict)
               and {"matchDate", "competitionName", "fixtureStateTypeId", "homeTeamGoals", "awayTeamGoals",
                    "homeTeam", "awayTeam", "canceledFixture", "notPlayedFixture", "postponedFixture"} <= row.keys()]
    if len(headers) != 1 or b'match-item-row-score finished' not in raw:
        return []
    row, = headers
    def entry(field):
        return values[row[field]]
    if (entry("competitionName") != "Liga Portugal Betclic" or entry("fixtureStateTypeId") != 5
            or any(entry(flag) is not False for flag in ("canceledFixture", "notPlayedFixture", "postponedFixture"))):
        return []
    kickoff = utc(entry("matchDate"))
    scores = [entry("homeTeamGoals"), entry("awayTeamGoals")]
    if kickoff >= stamp or any(type(goal) is not int or not 0 <= goal <= 30 for goal in scores):
        return []
    return [{"date": kickoff.date().isoformat(), "home": values[entry("homeTeam")["name"]],
             "away": values[entry("awayTeam")["name"]], "official_score": scores,
             "source": url, "source_match_id": urlsplit(url).path}]
