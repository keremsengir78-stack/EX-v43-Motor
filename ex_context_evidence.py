"""Bind reviewed absences and rotation to archived, timed workload observations."""

from datetime import timedelta
import re

from ex_history_archive import utc


def reviewed_context(bundle, fixture, workload, as_of, load_source):
    """Accept a complete review from the trusted review input after replaying its sources."""
    try:
        kickoff = utc(fixture["kickoff_at"])
        reviewed = utc(bundle["accepted_at"])
        if not kickoff - timedelta(hours=48) <= reviewed < as_of < kickoff:
            return None
        if bundle["fixture"] != {key: fixture[key] for key in ("event_id", "league", "team_ids", "kickoff_at")}:
            return None
        for side, club in fixture["team_ids"].items():
            if bundle["teams"][side]["team_id"] != club:
                return None
            load = workload[side]
            observations = load["completion_observations"]
            if not observations or load["rest_hours_since_archived_full_time_capped_at_336"] is None:
                return None
            if len({row["event_id"] for row in observations}) != len(observations):
                return None
            if any(not re.fullmatch(r"[0-9a-f]{64}", row.get("source_sha256") or "")
                   or not kickoff - timedelta(days=14) <= utc(row["kickoff_at"]) < utc(row["completion_upper_bound"])
                   <= utc(row["available_at"]) <= reviewed for row in observations):
                return None
            expected_rest = round(min(336, (kickoff - max(
                utc(row["completion_upper_bound"]) for row in observations)).total_seconds() / 3600), 2)
            if (load["rest_hours_since_archived_full_time_capped_at_336"] != expected_rest
                    or load["completed_match_count_14d_archived"] != len(observations)):
                return None
            for field in ("important_absences", "rotation"):
                item = bundle["teams"][side][field]
                if not isinstance(item["finding"], str) or not item["finding"].strip():
                    return None
                source = item["source"]
                if not kickoff - timedelta(hours=48) <= utc(item["published_at"]) <= utc(source["retrieved_at"]) <= reviewed:
                    return None
                load_source(source, source["url"])
        return {**bundle, "status": "CONTEXT_CROSS_VERIFIED", "workload": workload}
    except (KeyError, TypeError, AttributeError, ValueError, OSError):
        return None
