"""Capture future ESPN fixtures, venue, availability and market payloads as observed."""

import argparse
import datetime as dt
import json
from pathlib import Path

from ex_espn_provider import ESPN_LEAGUES
from ex_leagues import APPROVED_LEAGUES
from ex_history_archive import BudgetExhausted, HistoryArchive, atomic_write, paced_download, source_error, utc
from ex_history_sources import ESPN, identifier, teams
from run_ex_official_sources import ALTERNATE_CALENDARS, archive_alternate_calendars
from run_ex_pfl_discovery import prematch as pfl_prematch


LIVE_WINDOW = dt.timedelta(hours=48)
RESEARCH_WINDOW = dt.timedelta(hours=96)


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


def seed_recent_pregame(packs, archive, day):
    """Import only currently reusable evidence for this fixture date."""
    seen = set()
    now = archive.clock()
    for receipt in packs.glob("*/receipt.json"):
        seal = utc(json.loads(receipt.read_text())["created_at"])
        if seal >= now:
            continue
        candidates = [receipt.parent / filename for filename in ("forecasts/capture.json", "capture.json")]
        manifest_file = next((path for path in candidates if path.is_file()), None)
        if manifest_file is None:
            continue
        manifest = json.loads(manifest_file.read_text())
        if manifest["day"] != day.isoformat():
            continue
        source = HistoryArchive(receipt.parent / "pregame-cache", 0, clock=lambda: now)
        for report in manifest["reports"].values():
            for meta in [report["board"], *(row["source"] for row in report["records"])]:
                captured = utc(meta["retrieved_at"])
                if captured > seal:
                    raise ValueError("Archived pregame source postdates its receipt")
                identity = meta["url"], captured, meta["sha256"]
                crosses_live_window = any(
                    captured < utc(row["kickoff_at"]) - LIVE_WINDOW <= now
                    for row in report["records"]
                )
                if now - captured > dt.timedelta(minutes=20) or crosses_live_window or identity in seen:
                    continue
                raw, _ = source._load(meta, meta["url"])
                archive.import_capture(meta["url"], raw, captured, meta["sha256"])
                seen.add(identity)
    return len(seen)


def collect(archive, league, day, limit, *, horizon=LIVE_WINDOW):
    competition = ESPN_LEAGUES[league]
    board_url = f"{ESPN}/{competition}/scoreboard?dates={day:%Y%m%d}"
    ttl = dt.timedelta(minutes=20)
    fixtures, source = archive.get(
        board_url, lambda raw, stamp: prematch_fixtures(raw, stamp, day, competition, horizon),
        max_age=ttl)
    errors, records = [], []
    upcoming = [fixture for fixture in fixtures if archive.clock() < fixture[1]]
    for event_id, kickoff, sides in upcoming[:limit]:
        url = f"{ESPN}/{competition}/summary?event={event_id}"
        try:
            values, evidence = archive.get(url, lambda raw, stamp: summary(raw, stamp, event_id, kickoff, sides),
                                           max_age=ttl)
        except (BudgetExhausted, OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append(source_error("prematch", url, exc))
        else:
            records.append({"event_id": event_id, "kickoff_at": kickoff.isoformat(), "teams": sides,
                            "observed_fields": values, "source": evidence})
    return {"kind": "PREMATCH_CAPTURE", "league": league, "board": source, "records": records, "errors": errors,
            "eligible": len(upcoming), "requests": archive.requests, "ex_final_allowed": False}


def collect_registered(archive, day, limit, leagues=ESPN_LEAGUES, *, horizon=LIVE_WINDOW):
    reports, errors = {}, []
    for league in leagues:
        try:
            reports[league] = collect(archive, league, day, limit, horizon=horizon)
        except (BudgetExhausted, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append({"league": league, **source_error("board", None, exc)})
    return {"kind": "REGISTERED_LEAGUE_CAPTURE", "day": day.isoformat(), "reports": reports,
            "errors": errors, "registered_leagues": list(leagues), "requests": archive.requests,
            "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--league", choices=(*ESPN_LEAGUES, "all", "approved"), required=True)
    parser.add_argument("--day", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, choices=range(1, 26), default=18)
    args = parser.parse_args()
    scopes = {"all": ESPN_LEAGUES, "approved": APPROVED_LEAGUES}
    leagues = scopes.get(args.league, (args.league,))
    archive = HistoryArchive(args.cache, (args.limit + 1) * len(leagues), fetch=paced_download(.75))
    if not archive.clock().date() <= args.day <= archive.clock().date() + dt.timedelta(days=2):
        parser.error("Choose an upcoming UTC date within two days")
    report = (collect_registered(archive, args.day, args.limit, leagues) if args.league in scopes
              else collect(archive, args.league, args.day, args.limit))
    if args.league == "all":
        report["alternate_calendar_evidence"] = archive_alternate_calendars(
            ALTERNATE_CALENDARS, args.cache / "alternate-calendars")
        if "az.1" in ALTERNATE_CALENDARS:
            try:
                report["pfl_prematch_matches"] = pfl_prematch(args.cache / "pfl-pregame", args.day)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                report["pfl_prematch_issue"] = str(exc)
    atomic_write(args.output, (json.dumps(report, indent=2) + "\n").encode())
    groups = report.get("reports", {args.league: report})
    print(json.dumps({"eligible": sum(r["eligible"] for r in groups.values()),
                      "captured": sum(len(r["records"]) for r in groups.values()),
                      "leagues_responded": len(groups), "errors": report["errors"], "requests": report["requests"],
                      "alternate_calendars": {league: row["status"] for league, row in
                                              report.get("alternate_calendar_evidence", {}).items()}}))


if __name__ == "__main__":
    main()
