"""Reconstruct score-only history from sealed weekly ESPN scoreboards."""

import datetime as dt
import json
import re

from ex_history_archive import HistoryArchive, utc
from ex_history_sources import ESPN, teams
from ex_leagues import APPROVED_LEAGUES
from ex_retrospective import observed_season


def scoreboard_facts(packs, cutoff):
    allowed = {data[1] for data in APPROVED_LEAGUES.values()}
    pattern = re.compile(re.escape(ESPN) + r"/([^/]+)/scoreboard\?dates=([0-9]{8})")
    by_event = {}
    for receipt in packs.glob("*/receipt.json"):
        seal = utc(json.loads(receipt.read_text())["created_at"])
        if seal >= cutoff:
            continue
        report = json.loads((receipt.parent / "capacity.json").read_text())
        archive = HistoryArchive(receipt.parent / "cache", 0)
        for source in report["sources"]:
            link = pattern.fullmatch(source["url"])
            if not link or link[1] not in allowed:
                raise ValueError("Unexpected weekly scoreboard source")
            raw, captured = archive._load(source, source["url"])
            if captured > seal:
                raise ValueError("Weekly scoreboard evidence postdates receipt")
            payload = json.loads(raw)
            if {row["slug"] for row in payload["leagues"]} != {link[1]}:
                raise ValueError("Weekly scoreboard league mismatch")
            for event in payload["events"]:
                status = event["status"]["type"]
                if status.get("name") != "STATUS_FULL_TIME" or status.get("completed") is not True:
                    continue
                match, = event["competitions"]
                kickoff = utc(event["date"])
                if (match["id"] != event["id"] or utc(match["date"]) != kickoff
                        or kickoff.strftime("%Y%m%d") != link[2]
                        or captured < kickoff + dt.timedelta(minutes=90)):
                    continue
                scores = {side["homeAway"]: str(side.get("score")) for side in match["competitors"]}
                values = [scores[side] for side in ("home", "away")]
                if any(re.fullmatch(r"[0-9]{1,2}", value) is None or int(value) > 30 for value in values):
                    continue
                season, basis = observed_season(link[1], kickoff, event.get("season", {}).get("year"))
                row = {"event_id": event["id"], "teams": teams(match), "competition": link[1],
                       "kickoff": kickoff, "score": tuple(map(int, values)), "finished": captured,
                       "captured_at": seal, "season": season, "season_basis": basis,
                       "source_sha256": source["sha256"], "evidence_scope": "ESPN_SCOREBOARD_RESEARCH"}
                old = by_event.get(row["event_id"])
                if old and any(old[key] != row[key] for key in ("teams", "competition", "kickoff", "score")):
                    raise ValueError("Conflicting weekly scoreboard results")
                if not old or row["captured_at"] < old["captured_at"]:
                    by_event[row["event_id"]] = row
    return list(by_event.values())
