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
