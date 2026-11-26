"""Reconstruct score-only history from sealed weekly ESPN scoreboards."""

import datetime as dt
import json
import re

from ex_history_archive import HistoryArchive, utc
from ex_history_sources import ESPN, teams
from ex_leagues import APPROVED_LEAGUES, CUP_HISTORY_SLUGS
from ex_retrospective import observed_season
from run_ucl_baselines import verified_bytes


def scoreboard_facts(packs, cutoff, *, conflicts=None):
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
            for row in board_results(raw, link[1], link[2], captured, seal, source["sha256"]):
                old = by_event.get(row["event_id"])
                if old and any(old[key] != row[key] for key in ("teams", "competition", "kickoff", "score")):
                    if conflicts is None:
                        raise ValueError("Conflicting weekly scoreboard results")
                    conflicts.add(row["event_id"])
                    continue
                if not old or row["captured_at"] < old["captured_at"]:
                    by_event[row["event_id"]] = row
    return [row for event, row in by_event.items() if conflicts is None or event not in conflicts]


def board_results(raw, slug, day, captured, seal, digest):
    payload = json.loads(raw)
    if {row["slug"] for row in payload["leagues"]} != {slug}:
        raise ValueError("Weekly scoreboard league mismatch")
    for event in payload["events"]:
        status = event["status"]["type"]
        if status.get("name") != "STATUS_FULL_TIME" or status.get("completed") is not True:
            continue
        match, = event["competitions"]
        kickoff = utc(event["date"])
        if (match["id"] != event["id"] or utc(match["date"]) != kickoff
                or kickoff.strftime("%Y%m%d") != day
                or captured < kickoff + dt.timedelta(minutes=90)):
            continue
        scores = {side["homeAway"]: str(side.get("score")) for side in match["competitors"]}
        values = [scores[side] for side in ("home", "away")]
        if any(re.fullmatch(r"[0-9]{1,2}", value) is None or int(value) > 30 for value in values):
            continue
        season, basis = observed_season(slug, kickoff, event.get("season", {}).get("year"))
        yield {"event_id": event["id"], "teams": teams(match), "competition": slug,
               "kickoff": kickoff, "score": tuple(map(int, values)), "finished": captured,
               "captured_at": seal, "season": season, "season_basis": basis,
               "source_sha256": digest, "evidence_scope": "ESPN_SCOREBOARD_RESEARCH"}


def archived_domestic_boards(pack, cutoff, leagues=("de.2", "nl.2")):
    """Replay sealed, score-only evidence without inventing full-time timestamps."""
    report = pack / "domestic" / "report.json"
    if not report.is_file():
        return []
    sealed = utc(json.loads((pack / "receipt.json").read_text())["created_at"])
    if sealed >= cutoff:
        return []
    result = []
    for source in json.loads(report.read_bytes())["sources"]:
        league = source.get("league")
        if league not in leagues or source.get("error") or source.get("potentially_truncated"):
            continue
        slug = APPROVED_LEAGUES[league][1] if league in APPROVED_LEAGUES else CUP_HISTORY_SLUGS[league]
        day = dt.date.fromisoformat(source["date"]).strftime("%Y%m%d")
        stamp = utc(source["retrieved_at"])
        digest = source["sha256"]
        if (source["url"] != f"{ESPN}/{slug}/scoreboard?dates={day}"
                or stamp > sealed or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ValueError("Invalid archived domestic scoreboard provenance")
        raw = verified_bytes(report.parent / (digest + ".json"), digest)
        result.extend(board_results(raw, slug, day, stamp, sealed, digest))
    return result
