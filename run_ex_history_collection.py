"""Collect timestamped historical football evidence without fitting an EX model."""

import argparse
import datetime as dt
import json
from collections import Counter, defaultdict
from itertools import zip_longest
from pathlib import Path
from urllib.parse import urlsplit

from ex_history_archive import BudgetExhausted, HistoryArchive, atomic_write, source_error, utc
from ex_history_sources import ESPN, identifier, league_slug, match_detail, schedule, uefa_news


def collect_details(events, archive, shard=0, shards=1):
    """Stable assignment by provider event ID; a match has one owning shard."""
    details, errors, deferred = [], [], 0
    assigned = [event for event in events if int(event["event_id"]) % shards == shard]
    by_season = defaultdict(list)
    for event in assigned:
        by_season[str(event.get("source_season"))].append(event)
    ordered = (event for group in zip_longest(*by_season.values()) for event in group if event is not None)
    for event in ordered:
        competition = league_slug(event["competition"])
        event_id = identifier(event["event_id"])
        url = f"{ESPN}/{competition}/summary?event={event_id}"
        try:
            value, meta = archive.get(url, lambda raw, captured: match_detail(raw, captured, event),
                                      reusable=lambda item: item["completed"],
                                      content_schema="espn-summary-roster-v2")
        except BudgetExhausted:
            deferred += 1
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append(source_error("summary", url, exc))
        else:
            details.append({**value, "source": meta})
    return {"shard": shard, "shards": shards, "assigned": len(assigned), "match_details": details,
            "errors": errors, "deferred": deferred, "requests": archive.requests, "cache_hits": archive.cache_hits,
            "ex_final_allowed": False}


def collect(config, archive, *, plan_only=False):
    as_of = utc(config["as_of"])
    if as_of > archive.clock():
        raise ValueError("Collection cutoff cannot be in the future")
    start = utc(config["start"])
    if start >= as_of:
        raise ValueError("Invalid collection window")
    errors, events, calendars, details, previews = [], {}, [], [], []
    deferred = Counter()

    def read(stage, url, parse, **kwargs):
        try:
            return archive.get(url, parse, **kwargs)
        except BudgetExhausted:
            deferred[stage] += 1
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append(source_error(stage, url, exc))
        return None

    # Request each team/season only once. A shared fixture has a single detail per provider ID.
    seeds = {}
    for item in config["teams"]:
        team = identifier(item["espn_team_id"])
        season = item["season"]
        if type(season) is not int or not 2000 <= season <= 2100:
            raise ValueError("Invalid season year")
        seeds[team, season] = None
    if not seeds:
        raise ValueError("At least one team/season is required")
    for team, season in seeds:
        url = f"{ESPN}/all/teams/{team}/schedule?season={season}"
        parsed = read("schedule", url, lambda raw, _: schedule(raw, team, season),
                      max_age=dt.timedelta(days=7))
        if parsed is None:
            continue
        games, meta = parsed
        for event_id, event in games.items():
            if event_id in events and events[event_id] != event:
                raise ValueError(f"Conflicting calendars for event {event_id}")
            events[event_id] = event
        previous = None
        fixtures = []
        for event in sorted(games.values(), key=lambda record: record["kickoff_at"]):
            kickoff = utc(event["kickoff_at"])
            if kickoff >= as_of:
                continue
            if start <= kickoff:
                hrs = (kickoff - previous).total_seconds() / 3600 if previous and previous < kickoff else None
                fixtures.append({**event, "hours_since_previous_observed_kickoff": hrs})
            if event["completed"]:
                previous = kickoff
        calendars.append({"team_id": team, "season": season, "source": meta,
                          "complete_schedule_certified": False, "fixtures": fixtures})

    for media in config.get("uefa_articles", []):
        url = media["url"]
        parsed_url = urlsplit(url)
        if parsed_url.netloc != "www.uefa.com" or "/news/" not in parsed_url.path:
            raise ValueError("UEFA evidence must point to an official news article")
        for target in media["fixtures"]:
            try:
                stored = archive.prior_capture(url, utc(target["kickoff_at"]))
                if stored is not None:
                    raw, captured, meta = stored
                    for value in uefa_news(raw, captured, [target]):
                        previews.append({**value, "source": meta})
                    continue
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                errors.append(source_error("uefa_archive", url, exc))
                continue
            parsed = read("uefa", url, lambda raw, captured: uefa_news(raw, captured, [target]),
                          max_age=dt.timedelta(hours=6))
            if parsed is not None:
                values, meta = parsed
                previews.extend({**value, "source": meta} for value in values)

    pending = []
    for event in sorted(events.values(), key=lambda item: (item["kickoff_at"], item["event_id"]), reverse=True):
        if not event["completed"] or not start <= utc(event["kickoff_at"]) < as_of:
            continue
        pending.append(event)
    if not plan_only:
        result = collect_details(pending, archive)
        details.extend(result["match_details"])
        errors.extend(result["errors"])
        if result["deferred"]:
            deferred["summary"] += result["deferred"]
    players = [p for detail in details for p in detail["player_rows"]]
    return {
        "status": "PARTIAL_BUDGET" if deferred else "COMPLETE_WITH_SOURCE_GAPS" if errors else "COLLECTION_COMPLETE",
        "calendars": calendars, "match_details": details, "uefa_previews": previews,
        "coverage": {
            "schedule_seeds": len(seeds), "schedule_responses": len(calendars), "unique_schedule_events": len(events),
            "eligible_completed_events": len(pending), "summaries": len(details), "player_rows": len(players),
            "provider_minutes": sum(p["provider_minutes"] is not None for p in players),
            "nominal_regulation_minutes": sum(p["nominal_regulation_minutes"] is not None for p in players),
            "prematch_uefa_previews": sum(value["prematch_eligible"] for value in previews),
        },
        "requests": archive.requests, "cache_hits": archive.cache_hits, "deferred": dict(deferred), "errors": errors,
        "pending_events": pending if plan_only else [],
        "model_validation": {"status": "BLOCKED", "missing": [
            "certified all-competition coverage", "complete timestamped context and external effects",
            "independent prematch feature and settled score provenance",
        ]},
        "calibration_certified": False, "pup_allowed": False, "ex_final_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--plan", type=Path, help="Process a previously collected plan")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--profile", choices=("ucl", "all", "expanded"), default="ucl")
    parser.add_argument("--expansion", type=Path, default=Path("config/ex_history_expansion.json"))
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    parser.add_argument("--request-interval", type=float, default=.25)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget", type=int, default=30)
    parser.add_argument("--import-uefa-directory", type=Path,
                        help="Import a prior matchday_inputs/report.json and its original UEFA response")
    args = parser.parse_args()
    if not 1 <= args.budget <= 500:
        parser.error("--budget must be between 1 and 500")
    if not 0 <= args.shard < args.shards <= 32 or bool(args.config) == bool(args.plan):
        parser.error("Provide exactly one config or plan and a valid shard")
    if not .1 <= args.request_interval <= 30:
        parser.error("Request interval must be between 0.1 and 30 seconds")
    from ex_history_archive import paced_download
    archive = HistoryArchive(args.cache, args.budget, fetch=paced_download(args.request_interval))
    if args.plan:
        plan = json.loads(args.plan.read_text())
        report = collect_details(plan["pending_events"], archive, args.shard, args.shards)
        atomic_write(args.output, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
        print(json.dumps({key: value for key, value in report.items() if key != "match_details"}))
        return
    config = json.loads(args.config.read_text())
    if args.profile in {"all", "expanded"}:
        config["teams"].extend(config.get("main_teams", []))
    roster_evidence, roster_errors = [], []
    if args.profile == "expanded":
        from ex_espn_provider import ESPN_LEAGUES
        from ex_history_rosters import expand_rosters
        leagues = json.loads(args.expansion.read_text())["leagues"]
        for league, entry in leagues.items():
            if ESPN_LEAGUES.get(league) != entry["espn_competition"]:
                raise ValueError(f"Unknown expansion competition mapping: {league}")
            config["teams"].extend(entry["teams"])
        roster_evidence, roster_errors = expand_rosters(leagues, sorted({r["season"] for r in config["teams"]}), archive)
        config["teams"].extend({"espn_team_id": team, "season": record["season"]}
                               for record in roster_evidence for team in record.get("missing_seed_ids", []))
    if args.import_uefa_directory:
        meta = json.loads((args.import_uefa_directory / "report.json").read_text())["uefa_preview_source"]
        if Path(meta["file"]).name != meta["file"]:
            raise ValueError("Invalid imported evidence filename")
        archive.import_capture(meta["url"], (args.import_uefa_directory / meta["file"]).read_bytes(),
                               utc(meta["retrieved_at"]), meta["sha256"])
    report = collect(config, archive, plan_only=args.plan_only)
    if args.profile == "expanded":
        report["expansion_rosters"] = roster_evidence
        report["errors"].extend(roster_errors)
        report["coverage"]["standings_rosters_observed"] = sum("source" in r for r in roster_evidence)
        report["coverage"]["standings_rosters_targeted"] = len(roster_evidence)
    atomic_write(args.output, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({key: report[key] for key in ("status", "coverage", "requests", "cache_hits", "deferred", "errors")}))
    if not report["calendars"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
