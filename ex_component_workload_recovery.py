"""Reconstruct a research workload from completed events and a bounded schedule."""

from datetime import timedelta
import re

from ex_history_archive import utc


COMPLETED = {"STATUS_FULL_TIME", "STATUS_FINAL_AET", "STATUS_FINAL_PEN"}


def recover_team_workload(schedule, observations, team, kickoff, as_of, *, allow_kickoff_proxy=False):
    """Use the prior match's explicit finish and count only completed events."""
    try:
        if not as_of < kickoff:
            return None, "TARGET_ALREADY_STARTED"
        horizon = kickoff - timedelta(days=14)
        ordered = sorted(schedule["matches_shown"], key=lambda row: utc(row["kickoff_at"]))
        if not ordered or utc(ordered[0]["kickoff_at"]) >= horizon:
            return None, "SCHEDULE_DOES_NOT_COVER_14_DAY_BOUNDARY"
        recent = [row for row in ordered if horizon <= utc(row["kickoff_at"]) < as_of]
        if not recent or len({row["event_id"] for row in recent}) != len(recent):
            return None, "RECENT_SCHEDULE_INCOMPLETE_OR_DUPLICATE"
        completed = []
        for match in recent:
            record = observations.get(match["event_id"], {})
            fact, source = record.get("fact", {}), record.get("source", {})
            if (fact.get("provider_completed") is not True or fact.get("terminal_status") not in COMPLETED
                    or team not in fact["teams"].values()
                    or utc(fact["kickoff"]) != utc(match["kickoff_at"])
                    or not re.fullmatch(r"[0-9a-f]{64}", source.get("sha256", ""))
                    or not utc(fact["kickoff"]) < utc(source["retrieved_at"]) < as_of):
                return None, "COMPLETED_MATCH_PROOF_MISSING"
            completed.append(record)
        last = completed[-1]["fact"]
        if last.get("terminal_source") != "PROVIDER_END_REGULAR_TIME":
            if not allow_kickoff_proxy:
                return None, "LATEST_MATCH_FINISH_UNVERIFIED"
            return {
                "kickoff_gap_hours": (kickoff - utc(last["kickoff"])).total_seconds() / 3600,
                "completed_match_count": len(completed),
                "basis": "KICKOFF_TO_KICKOFF_PROXY",
                "matches": completed,
            }, None
        finished = utc(last["finished"])
        if not utc(last["kickoff"]) < finished <= utc(completed[-1]["source"]["retrieved_at"]):
            return None, "LATEST_MATCH_FINISH_INVALID"
        rest_hours = (kickoff - finished).total_seconds() / 3600
        return {"rest_hours": rest_hours, "completed_match_count": len(completed),
                "features": (min(rest_hours, 336) / 336, len(completed) / 5),
                "matches": completed}, None
    except (KeyError, ValueError, TypeError, AttributeError):
        return None, "WORKLOAD_SOURCE_INVALID"


def completion_tasks(rows, known, cutoff):
    """Deduplicate missing recent-match evidence across target teams and days."""
    tasks = {}
    for row in rows:
        kickoff = utc(row["fixture"]["kickoff_at"])
        if kickoff <= cutoff:
            continue
        for side, context in row["observed_inputs"]["workload"].items():
            team = row["fixture"]["team_ids"][side]
            observed = {item["event_id"] for item in context.get("completion_observations", ())}
            for event in (context.get("source_recent_schedule") or {}).get("matches_shown", ()):
                if (event["event_id"] not in known and event["event_id"] not in observed
                        and kickoff - timedelta(days=14) <= utc(event["kickoff_at"]) < cutoff):
                    tasks.setdefault(event["event_id"], []).append((team, event))
    return tasks


def parse_completion(raw, captured, event_id, claims):
    """Verify a league-independent summary against the archived schedule claims."""
    import json

    payload = json.loads(raw)
    header = payload["header"]
    competition, = header["competitions"]
    stamp = utc(competition["date"])
    teams = {row["homeAway"]: row["team"]["id"] for row in competition["competitors"]}
    status = competition["status"]["type"]
    slug = header["league"]["slug"]
    if (header["id"] != event_id or competition["id"] != event_id
            or set(teams) != {"home", "away"} or len(set(teams.values())) != 2
            or not re.fullmatch(r"[a-z0-9._-]+", slug)
            or any(utc(event["kickoff_at"]) != stamp or team not in teams.values()
                   or event.get("teams", teams) != teams for team, event in claims)
            or captured <= stamp
            or status.get("state") != "post" or status.get("completed") is not True
            or status.get("name") not in COMPLETED):
        raise ValueError("Unverified completed match or conflicting schedule identity")
    return {"event_id": event_id, "competition": slug, "teams": teams, "kickoff": stamp.isoformat(),
            "provider_completed": True, "terminal_status": status["name"]}


def collect_completions(tasks, archive):
    """Fetch one canonical lookup per event and preserve source and failure receipts."""
    from ex_history_archive import BudgetExhausted, RetryDeferred
    from ex_history_sources import ESPN

    found, issues = {}, {}
    for event_id, claims in tasks.items():
        if not isinstance(event_id, str) or not re.fullmatch(r"[0-9]+", event_id):
            issues[event_id] = "INVALID_EVENT_ID"
            continue
        url = f"{ESPN}/all/summary?event={event_id}"
        try:
            fact, source = archive.get(url, lambda raw, at: parse_completion(raw, at, event_id, claims),
                                       content_schema="completed-workload-event-v1")
            found[event_id] = {"fact": fact, "source": source}
        except (OSError, ValueError, TypeError, KeyError, AttributeError, BudgetExhausted, RetryDeferred) as exc:
            issues[event_id] = {"source": url, "reason": str(exc) or type(exc).__name__}
    return found, issues
