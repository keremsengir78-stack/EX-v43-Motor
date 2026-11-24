"""Collect timestamped historical football evidence without fitting an EX model."""

import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from ex_history_archive import BudgetExhausted, HistoryArchive, atomic_write, utc
from ex_history_sources import ESPN, identifier, match_detail, schedule, uefa_news


def collect(config, archive):
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
            errors.append({"stage": stage, "url": url, "error": str(exc)})
        return None

    # Request each team/season only once. A shared fixture has a single detail per provider ID.
    seeds = set()
    for item in config["teams"]:
        team = identifier(item["espn_team_id"])
        season = item["season"]
        if type(season) is not int or not 2000 <= season <= 2100:
            raise ValueError("Invalid season year")
        seeds.add((team, season))
    if not seeds:
        raise ValueError("At least one team/season is required")
    for team, season in sorted(seeds):
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
                errors.append({"stage": "uefa_archive", "url": url, "error": str(exc)})
                continue
            parsed = read("uefa", url, lambda raw, captured: uefa_news(raw, captured, [target]),
                          max_age=dt.timedelta(hours=6))
            if parsed is not None:
                values, meta = parsed
                previews.extend({**value, "source": meta} for value in values)

    for event in sorted(events.values(), key=lambda item: (item["kickoff_at"], item["event_id"]), reverse=True):
        if not event["completed"] or not start <= utc(event["kickoff_at"]) < as_of:
            continue
        url = f"{ESPN}/{event['competition']}/summary?event={event['event_id']}"
        parsed = read("summary", url, lambda raw, captured: match_detail(raw, captured, event),
                      reusable=lambda item: item["completed"])
        if parsed is not None:
            value, meta = parsed
            details.append({**value, "source": meta})
    players = [p for detail in details for p in detail["player_rows"]]
    return {
        "status": "PARTIAL_BUDGET" if deferred else "COMPLETE_WITH_SOURCE_GAPS" if errors else "COLLECTION_COMPLETE",
        "calendars": calendars, "match_details": details, "uefa_previews": previews,
        "coverage": {
            "schedule_seeds": len(seeds), "schedule_responses": len(calendars), "unique_schedule_events": len(events),
            "summaries": len(details), "player_rows": len(players),
            "provider_minutes": sum(p["provider_minutes"] is not None for p in players),
            "nominal_regulation_minutes": sum(p["nominal_regulation_minutes"] is not None for p in players),
            "prematch_uefa_previews": sum(value["prematch_eligible"] for value in previews),
        },
        "requests": archive.requests, "cache_hits": archive.cache_hits, "deferred": dict(deferred), "errors": errors,
        "model_validation": {"status": "BLOCKED", "missing": [
            "certified all-competition coverage", "complete timestamped context and external effects",
            "independent prematch feature and settled score provenance",
        ]},
        "calibration_certified": False, "pup_allowed": False, "ex_final_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--budget", type=int, default=30)
    parser.add_argument("--import-uefa-directory", type=Path,
                        help="Import a prior matchday_inputs/report.json and its original UEFA response")
    args = parser.parse_args()
    if not 1 <= args.budget <= 500:
        parser.error("--budget must be between 1 and 500")
    config = json.loads(args.config.read_text())
    archive = HistoryArchive(args.cache, args.budget)
    if args.import_uefa_directory:
        meta = json.loads((args.import_uefa_directory / "report.json").read_text())["uefa_preview_source"]
        if Path(meta["file"]).name != meta["file"]:
            raise ValueError("Invalid imported evidence filename")
        archive.import_capture(meta["url"], (args.import_uefa_directory / meta["file"]).read_bytes(),
                               utc(meta["retrieved_at"]), meta["sha256"])
    report = collect(config, archive)
    atomic_write(args.output, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({key: report[key] for key in ("status", "coverage", "requests", "cache_hits", "deferred", "errors")}))
    if not report["calendars"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
