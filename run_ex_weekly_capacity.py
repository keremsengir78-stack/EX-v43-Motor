"""Count unique published fixtures for the 13 approved competitions."""

import argparse
from collections import Counter, defaultdict
import datetime as dt
import json
from pathlib import Path
from statistics import mean

from ex_daily_research import MARKET_KEYS
from ex_decision import MARKETS
from ex_historical_features import market_labels

from ex_history_archive import HistoryArchive, atomic_write, paced_download, source_error, utc
from ex_history_sources import ESPN, identifier, teams
from ex_leagues import APPROVED_LEAGUES
from run_ex_production_coverage import calibration_sensitivity
from run_ex_prospective_pipeline import combine_forecasts, read_forecast_pack
from run_ex_prospective_validation import join_holdout


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
        rows[event_id] = {"kickoff": kickoff.isoformat(), "teams": teams(match), "status": state,
                          "names": {side["homeAway"]: side["team"]["displayName"] for side in match["competitors"]}}
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


def observed_coverage(fixtures, packs, settlements=None, *, fixture_phases=None):
    forecasts = combine_forecasts(read_forecast_pack(p) for p in packs.glob("*/receipt.json"))
    by_league = {league: Counter() for league in APPROVED_LEAGUES}
    for row in forecasts:
        fixture = fixtures.get(row["event_id"])
        if fixture is None:
            continue
        if (row["league"] != fixture["league"] or row["teams"] != fixture["teams"]
                or utc(row["kickoff"]) != utc(fixture["kickoff"])):
            raise ValueError("Archived forecast and weekly fixture identity disagree")
        counts = by_league[row["league"]]
        counts["sealed_research_forecasts"] += 1
        counts["full_strength_window"] += row["strength"] is not None
    phase = defaultdict(set)
    domestic = {}
    for receipt in packs.glob("*/receipt.json"):
        meta = json.loads(receipt.read_text())
        sealed = utc(meta["created_at"])
        for name in ("forecasts/capture.json", "capture.json"):
            capture = receipt.parent / name
            if not capture.is_file():
                continue
            for league, report in json.loads(capture.read_text())["reports"].items():
                for row in report["records"]:
                    event = row["event_id"]
                    fixture = fixtures.get(event)
                    if (fixture and fixture["league"] == league and row["teams"] == fixture["teams"]
                            and utc(row["kickoff_at"]) == utc(fixture["kickoff"])
                            and utc(row["source"]["retrieved_at"]) <= sealed < utc(fixture["kickoff"])):
                        phase["prematch_archived"].add(event)
        daily = receipt.parent / "forecasts/daily-analysis.json"
        if not daily.is_file():
            continue
        for row in json.loads(daily.read_text()):
            identity = row["fixture"]
            event = identity["event_id"]
            fixture = fixtures.get(event)
            if (fixture and fixture["league"] == identity["league"] and fixture["teams"] == identity["team_ids"]
                    and utc(fixture["kickoff"]) == utc(identity["kickoff_at"])
                    and utc(row["as_of"]) <= sealed < utc(fixture["kickoff"])
                    and (row["domestic_research"] or {}).get("baseline")):
                baseline = row["domestic_research"]["baseline"]
                probabilities = {market: baseline.get(MARKET_KEYS[market]) for market in MARKETS}
                if not all(type(value) in (int, float) and 0 <= value <= 1 for value in probabilities.values()):
                    continue
                phase["domestic_research_baselines"].add(event)
                prior = domestic.get(event)
                if prior and prior[0] == sealed and prior[1] != probabilities:
                    raise ValueError("Conflicting domestic forecasts sealed at the same instant")
                if prior is None or sealed < prior[0]:
                    domestic[event] = sealed, probabilities
    joined_outcomes = {}
    forecast_ids = {row["event_id"] for row in forecasts}
    if settlements:
        for receipt in settlements.glob("*/receipt.json"):
            for name in ("settlement/outcomes.jsonl", "outcomes.jsonl",
                         "settlement/tracked-verified-outcomes.jsonl", "tracked-verified-outcomes.jsonl"):
                ledger = receipt.parent / name
                if not ledger.is_file():
                    continue
                for line in ledger.read_text().splitlines():
                    row = json.loads(line)
                    event = row["event_id"]
                    fixture = fixtures.get(event)
                    if (fixture and (event in forecast_ids or event in domestic)
                            and fixture["league"] == row["league"] and fixture["teams"] == row["teams"]
                            and utc(fixture["kickoff"]) == utc(row["kickoff"])
                            and utc(row["kickoff"]) < utc(row["settled_at"])
                            and row.get("official_review", {}).get("scope") == "REVIEWED_OFFICIAL_RESULT"):
                        if row["labels"] != market_labels(*row["score"]):
                            raise ValueError("Archived result labels disagree with the score")
                        existing = joined_outcomes.setdefault(event, row)
                        if existing["labels"] != row["labels"] or existing["score"] != row["score"]:
                            raise ValueError("Conflicting corroborated outcomes across archived packs")
                        if event in forecast_ids:
                            phase["independently_settled_venue5"].add(event)
                        if event in domestic:
                            phase["independently_settled_domestic"].add(event)
    for column, events in phase.items():
        for event in events:
            by_league[fixtures[event]["league"]][column] += 1
    columns = ("prematch_archived", "sealed_research_forecasts", "domestic_research_baselines",
               "full_strength_window", "independently_settled_venue5", "independently_settled_domestic", "full_model_verified")
    if fixture_phases is not None:
        fixture_phases.update(phase)
    rows = join_holdout(forecasts, [row for event, row in joined_outcomes.items() if event in forecast_ids])
    domestic_events = phase["independently_settled_domestic"]
    performance = {
        "status": "DESCRIPTIVE_ONLY" if rows else "NO_INDEPENDENT_OUTCOMES",
        "matched": len(rows),
        "venue5_brier": {m: mean((r["short"][m] - r["labels"][m]) ** 2 for r in rows) for m in MARKETS}
        if rows else {},
        "domestic_research": {"matched": len(domestic_events),
                              "brier": {m: mean((domestic[e][1][m] - joined_outcomes[e]["labels"][m]) ** 2
                                                for e in sorted(domestic_events)) for m in MARKETS}
                              if domestic_events else {}},
        "production_allowed": False,
    }
    return {league: {key: counts[key] for key in columns} for league, counts in by_league.items()}, performance


def seed_cached_boards(packs, archive, week_start):
    """Restore prior verified boards for this week before refreshing stale URLs."""
    total = 0
    for report_path in packs.glob("*/capacity.json"):
        report = json.loads(report_path.read_text())
        if report["week_start"] != str(week_start):
            continue
        cache = HistoryArchive(report_path.parent / "cache", 0)
        for source in report["sources"]:
            url = source["url"]
            raw, stamp = cache._load(source, url)
            archive.import_capture(url, raw, stamp, source["sha256"])
            total += 1
    return total


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week-start", type=dt.date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--packs", type=Path)
    parser.add_argument("--prior-weeks", type=Path)
    parser.add_argument("--settlements", type=Path)
    parser.add_argument("--examples", type=Path)
    args = parser.parse_args()
    if args.week_start.weekday() != 0:
        parser.error("Week starts on Monday UTC")
    archive = HistoryArchive(args.output / "cache", 7 * len(APPROVED_LEAGUES), fetch=paced_download(.75))
    if args.prior_weeks:
        seed_cached_boards(args.prior_weeks, archive, args.week_start)
    result = collect(archive, args.week_start)
    result["network_requests"] = archive.requests
    result["cached_boards"] = archive.cache_hits
    if args.packs:
        phases = {}
        coverage, result["weekly_performance"] = observed_coverage(
            result["fixtures"], args.packs, args.settlements, fixture_phases=phases)
        result["observed_coverage"] = coverage
        totals = {key: sum(row[key] for row in coverage.values()) for key in next(iter(coverage.values()))}
        fixtures = result["published_fixtures"]
        result["phase_totals"] = totals
        measured_at = archive.clock()
        opened = {event for event, row in result["fixtures"].items()
                  if utc(row["kickoff"]) - dt.timedelta(hours=48) <= measured_at}
        result["capture_window"] = {"measured_at": measured_at.isoformat(), "window_hours": 48,
            "opened": len(opened), "not_due": fixtures - len(opened),
            "prematch_coverage_of_due": totals["prematch_archived"] / len(opened) if opened else None}
        prematch = phases.get("prematch_archived", set())
        result["fixture_capture_status"] = {
            event: ("PREMATCH_ARCHIVED" if event in prematch else
                    "PREMATCH_WINDOW_CLOSED_WITHOUT_EVIDENCE" if utc(row["kickoff"]) <= measured_at else
                    "PREMATCH_PENDING" if event in opened else "NOT_DUE")
            for event, row in result["fixtures"].items()}
        result["phase_share_of_published"] = {key: count / fixtures if fixtures else None
                                               for key, count in totals.items()}
    if args.examples:
        examples = [json.loads(line) for line in args.examples.read_text().splitlines()]
        rates = (result["published_fixtures"],)
        result["retrospective_sizing"] = calibration_sensitivity(examples, rates)
    atomic_write(args.output / "capacity.json", (json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps({k: result[k] for k in ("week_start", "published_fixtures", "boards_observed",
                                             "by_league", "board_failures")}))


if __name__ == "__main__":
    main()
