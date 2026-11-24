"""Validate and merge sharded collection and expose evidence-scoped EX features."""

import argparse
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path

from ex_historical_features import provider_context
from ex_history_archive import BudgetExhausted, HistoryArchive, atomic_write, failure_class, paced_download, utc
from ex_history_environment import coordinates, nasa_power_at, separation_km, weather_at


def assemble(plan, parts):
    events = {event["event_id"]: event for event in plan["pending_events"]}
    if len(events) != len(plan["pending_events"]):
        raise ValueError("Duplicate plan event")
    shards = len(parts)
    slots = {part["shard"] for part in parts}
    if not parts or slots != set(range(shards)) or any(part["shards"] != shards for part in parts):
        raise ValueError("Incomplete or conflicting collection shards")
    found, coverage = {}, defaultdict(Counter)
    for event in events.values():
        coverage[event["competition"]]["planned"] += 1
    for part in parts:
        owner = part["shard"]
        assigned = sum(int(key) % shards == owner for key in events)
        if part["assigned"] != assigned:
            raise ValueError("Shard and plan counts differ")
        for detail in part["match_details"]:
            key = detail["event_id"]
            if (key not in events or key in found or int(key) % shards != owner
                    or detail["teams"] != events[key]["teams"]
                    or utc(detail["kickoff_at"]) != utc(events[key]["kickoff_at"])):
                raise ValueError(f"Invalid summary shard ownership or fixture identity: {key}")
            found[key] = detail
            count = coverage[events[key]["competition"]]
            count["summaries"] += 1
            count["completed_summaries"] += int(detail["completed"])
            count["venue_observations"] += int(bool(detail["venue"]))
            count["summaries_with_roster_identity_conflicts"] += int(bool(detail.get("roster_identity_conflicts")))
            for row in detail["player_rows"]:
                count["player_rows"] += 1
                count["provider_minutes"] += int(row["provider_minutes"] is not None)
                count["nominal_minutes"] += int(row["nominal_regulation_minutes"] is not None)
    return found, {league: {**counts, "summary_fraction": counts["completed_summaries"] / counts["planned"]}
                   for league, counts in sorted(coverage.items())}


def summarize(plan, parts, archive, venues):
    details, coverage = assemble(plan, parts)
    now = archive.clock()
    weather, weather_errors = {}, []
    for event, detail in sorted(details.items(), key=lambda item: utc(item[1]["kickoff_at"])):
        point = coordinates(detail["venue"], venues)
        if point is None or now - utc(detail["kickoff_at"]) < dt.timedelta(days=7):
            continue
        for provider, fetch in (("Open-Meteo", weather_at), ("NASA POWER", nasa_power_at)):
            try:
                weather[event] = {"provider": provider, **fetch(archive, point, detail["kickoff_at"])}
            except BudgetExhausted:
                break
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                weather_errors.append({"event_id": event, "provider": provider,
                                       "category": failure_class(exc), "error": str(exc)})
            else:
                break
    travel = []
    contexts = []
    for calendar in plan["calendars"]:
        contexts.append({"team_id": calendar["team_id"], "season": calendar["season"],
                         **provider_context(calendar, details, now.isoformat())})
        previous = None
        for fixture in sorted(calendar["fixtures"], key=lambda event: event["kickoff_at"]):
            if not fixture["completed"]:
                continue
            detail = details.get(fixture["event_id"], {})
            current = coordinates(detail.get("venue"), venues)
            if previous is not None and current is not None:
                previous_event, previous_point, previous_venue = previous
                travel.append({
                    "team_id": calendar["team_id"], "from_event": previous_event, "to_event": fixture["event_id"],
                    "distance_km": separation_km(previous_point, current), "kind": "VENUE_GEODESIC_PROXY",
                    "coordinate_sources": [venues[previous_venue]["source"], venues[str(detail["venue"]["id"])]["source"]],
                })
            previous = (fixture["event_id"], current, str(detail["venue"]["id"])) if current is not None else None
    balanced, complete = 0, 0
    for detail in details.values():
        minutes = defaultdict(list)
        for row in detail["player_rows"]:
            minutes[row["team_id"]].append(row["nominal_regulation_minutes"])
        for values in minutes.values():
            if values and all(value is not None for value in values):
                complete += 1
                balanced += int(sum(values) == 990)
    errors = plan["errors"] + [error for part in parts for error in part["errors"]]
    placeholder = sum(not detail["completed"] for detail in details.values())
    return {
        "as_of": now.isoformat(), "calendar_coverage": plan["coverage"],
        "competition_coverage": coverage, "completed_summaries": len(details) - placeholder,
        "summary_fraction": (len(details) - placeholder) / len(plan["pending_events"]) if plan["pending_events"] else 0,
        "requested_summaries": sum(part["requests"] for part in parts),
        "summary_cache_hits": sum(part["cache_hits"] for part in parts),
        "deferred_summaries": sum(part["deferred"] for part in parts),
        "errors": errors,
        "source_failure_counts": dict(Counter(error.get("category", "LEGACY_UNCLASSIFIED")
                                     for error in errors)),
        "weather": weather, "weather_errors": weather_errors,
        "venue_geodesic_transitions": travel, "verified_travel_observations": [], "observed_team_contexts": contexts,
        "minute_arithmetic": {"complete_nominal_team_totals": complete, "balanced_990": balanced},
        "model_validation": plan["model_validation"], "calibration_certified": False, "ex_final_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--parts", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--venues", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    parts = [json.loads(path.read_text()) for path in sorted(args.parts.rglob("*.json"))]
    result = summarize(plan, parts, HistoryArchive(args.cache, 12, fetch=paced_download(.5)),
                       json.loads(args.venues.read_text()))
    atomic_write(args.output, (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({**{key: result[key] for key in ("calendar_coverage", "completed_summaries", "summary_fraction",
                                                     "requested_summaries", "summary_cache_hits", "deferred_summaries",
                                                     "minute_arithmetic", "source_failure_counts")},
                      "weather_observations": len(result["weather"]),
                      "weather_observations_by_provider": dict(Counter(
                          item["provider"] for item in result["weather"].values())),
                      "roster_identity_conflict_summaries": sum(
                          league.get("summaries_with_roster_identity_conflicts", 0)
                          for league in result["competition_coverage"].values()),
                      "weather_failure_counts": dict(Counter(f"{e['provider']}:{e['category']}"
                                                             for e in result["weather_errors"]))}))


if __name__ == "__main__":
    main()
