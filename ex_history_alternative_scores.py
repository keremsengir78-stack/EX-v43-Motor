"""Bundesliga score observations from a separate published archive."""

import datetime as dt
import json

OPENLIGA = "https://api.openligadb.de/getmatchdata/bl1"


def bundesliga_scores(raw, season, as_of):
    rows = []
    seen = set()
    for event in json.loads(raw):
        if event["leagueShortcut"] != "bl1" or int(event["leagueSeason"]) != season:
            raise ValueError("OpenLigaDB league or season mismatch")
        day = dt.datetime.fromisoformat(event["matchDateTime"]).date().isoformat()
        if not event["matchIsFinished"] or day >= as_of:
            continue
        results = [r for r in event["matchResults"] if r["resultTypeID"] == 2]
        if len(results) != 1:
            continue
        result, = results
        score = result["pointsTeam1"], result["pointsTeam2"]
        if any(type(goal) is not int or not 0 <= goal <= 30 for goal in score):
            raise ValueError("Invalid Bundesliga final score")
        home, away = event["team1"]["teamName"].strip(), event["team2"]["teamName"].strip()
        key = day, home, away
        if not home or not away or home == away or key in seen:
            raise ValueError("Invalid or duplicate Bundesliga fixture")
        seen.add(key)
        rows.append({"date": day, "league": "de.1", "home": home, "away": away,
                     "home_goals": score[0], "away_goals": score[1]})
    if not rows:
        raise ValueError("No finished Bundesliga results before cutoff")
    return rows
