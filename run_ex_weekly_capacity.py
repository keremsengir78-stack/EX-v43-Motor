"""Count unique published fixtures for the 13 approved competitions."""

import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path

from ex_history_archive import HistoryArchive, atomic_write, paced_download, source_error, utc
from ex_history_sources import ESPN, identifier, teams
from ex_leagues import APPROVED_LEAGUES


def board(raw, slug, day):
    payload = json.loads(raw)
    if {entry["slug"] for entry in payload["leagues"]} != {slug}:
        raise ValueError("Competition identity mismatch")
    rows = {}
    for event in payload["events"]:
        event_id = identifier(event["id"])
        kickoff = utc(event["date"])
        state = event["status"]["type"]["name"]
        if kickoff.date() != day or state in {"STATUS_CANCELED", "STATUS_CANCELLED", "STATUS_POSTPONED", "STATUS_ABANDONED"}:
            continue
        match, = event["competitions"]
        if match["id"] != event_id or utc(match["date"]) != kickoff or event_id in rows:
            raise ValueError("Invalid or duplicate fixture identity")
        rows[event_id] = {"kickoff": kickoff.isoformat(), "teams": teams(match), "status": state}
    return rows


def collect(archive, start):
    fixtures, failures, by_league, sources = {}, [], Counter(), []
    for league, (_, slug, _, _) in APPROVED_LEAGUES.items():
        for offset in range(7):
            day = start + dt.timedelta(days=offset)
            url = f"{ESPN}/{slug}/scoreboard?dates={day:%Y%m%d}"
            try:
                rows, source = archive.get(url, lambda raw, _: board(raw, slug, day),
                                           max_age=dt.timedelta(hours=12))
            except (OSError, ValueError, TypeError, KeyError) as exc:
                failures.append({"league": league, "day": str(day), **source_error("weekly_board", url, exc)})
                continue
            sources.append(source)
            for event, info in rows.items():
                if event in fixtures:
                    raise ValueError("Duplicate fixture across weekly league boards")
                fixtures[event] = {"league": league, **info}
                by_league[league] += 1
    return {"week_start": str(start), "by_league": {k: by_league[k] for k in APPROVED_LEAGUES},
            "published_fixtures": len(fixtures), "boards_observed": len(sources),
            "board_failures": failures, "fixture_inventory_complete": not failures, "sources": sources,
            "fixtures": fixtures, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-start", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.week_start.weekday() != 0:
        parser.error("Week starts on Monday UTC")
    archive = HistoryArchive(args.output / "cache", 7 * len(APPROVED_LEAGUES), fetch=paced_download(.75))
    result = collect(archive, args.week_start)
    atomic_write(args.output / "capacity.json", (json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("week_start", "published_fixtures", "boards_observed",
                                             "by_league", "board_failures")}))


if __name__ == "__main__":
    main()
