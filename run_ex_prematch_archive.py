"""Capture future ESPN fixtures, venue, availability and market payloads as observed."""

import argparse
import datetime as dt
import json
from pathlib import Path

from ex_espn_provider import ESPN_LEAGUES
from ex_history_archive import HistoryArchive, atomic_write, paced_download, source_error, utc
from ex_history_sources import ESPN, identifier, teams


def prematch_fixtures(raw, captured, day, competition, horizon):
    payload = json.loads(raw)
    if {league["slug"] for league in payload["leagues"]} != {competition}:
        raise ValueError("ESPN board competition mismatch")
    fixtures = []
    for event in payload["events"]:
        kickoff = utc(event["date"])
        state = event["status"]["type"]
        if kickoff.date() != day or not captured < kickoff <= captured + horizon or state["state"] != "pre":
            continue
        match, = event["competitions"]
        event_id = identifier(event["id"])
        if match["id"] != event_id or utc(match["date"]) != kickoff:
            raise ValueError("ESPN fixture and competition mismatch")
        fixtures.append((event_id, kickoff, teams(match)))
    return fixtures


def summary(raw, captured, event_id, kickoff, sides):
    payload = json.loads(raw)
    header = payload["header"]
    match, = header["competitions"]
    usage = match["status"]["type"]
    if (header["id"] != event_id or match["id"] != event_id or utc(match["date"]) != kickoff
            or teams(match) != sides or captured >= kickoff or usage["state"] != "pre"
            or usage.get("completed") is True):
        raise ValueError("Summary is not a capture of the requested fixture before kickoff")
    return {"venue_observed": bool(payload.get("gameInfo", {}).get("venue")),
            "quote_payload_observed": bool(payload.get("odds") or payload.get("pickcenter")
                                           or payload.get("hasOdds")),
            "roster_payload_observed": bool(payload.get("rosters"))}


def collect(archive, league, day, limit):
    competition = ESPN_LEAGUES[league]
    board_url = f"{ESPN}/{competition}/scoreboard?dates={day:%Y%m%d}"
    ttl = dt.timedelta(minutes=20)
    fixtures, source = archive.get(
        board_url, lambda raw, stamp: prematch_fixtures(raw, stamp, day, competition, dt.timedelta(hours=48)),
        max_age=ttl)
    errors, records = [], []
    upcoming = [fixture for fixture in fixtures if archive.clock() < fixture[1]]
    for event_id, kickoff, sides in upcoming[:limit]:
        url = f"{ESPN}/{competition}/summary?event={event_id}"
        try:
            values, evidence = archive.get(url, lambda raw, stamp: summary(raw, stamp, event_id, kickoff, sides),
                                           max_age=ttl)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append(source_error("prematch", url, exc))
        else:
            records.append({"event_id": event_id, "kickoff_at": kickoff.isoformat(), "teams": sides,
                            "observed_fields": values, "source": evidence})
    return {"kind": "PREMATCH_CAPTURE", "board": source, "records": records, "errors": errors,
            "eligible": len(upcoming), "requests": archive.requests, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", choices=ESPN_LEAGUES, required=True)
    parser.add_argument("--day", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, choices=range(1, 26), default=18)
    args = parser.parse_args()
    archive = HistoryArchive(args.cache, args.limit + 1, fetch=paced_download(.75))
    if not archive.clock().date() <= args.day <= archive.clock().date() + dt.timedelta(days=2):
        parser.error("Choose an upcoming UTC date within two days")
    report = collect(archive, args.league, args.day, args.limit)
    atomic_write(args.output, (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps({"eligible": report["eligible"], "captured": len(report["records"]),
                      "errors": report["errors"], "requests": report["requests"]}))


if __name__ == "__main__":
    main()
