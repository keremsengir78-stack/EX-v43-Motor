"""Review timed live-window captures without replaying research forecasts."""

import argparse
from collections import Counter
import datetime as dt
import json
from pathlib import Path

from ex_fixture_odds import check_odds
from ex_history_sources import ESPN
from ex_history_archive import HistoryArchive, atomic_write, utc
from run_ex_prematch_archive import LIVE_WINDOW, prematch_fixtures, summary
from run_ex_prospective_pipeline import market_quote_chain
from run_ucl_matchday_inputs import observed_load
from ex_espn_provider import ESPN_LEAGUES


def review_capture(manifest, cache, targets, cutoff):
    rows, issues = [], []
    day = dt.date.fromisoformat(manifest["day"])
    for league, report in manifest["reports"].items():
        board = report["board"]
        competition = ESPN_LEAGUES[league]
        board_raw, board_at = cache._load(board, f"{ESPN}/{competition}/scoreboard?dates={day:%Y%m%d}")
        events = {row["id"]: row for row in json.loads(board_raw)["events"]}
        qualified = {event: (kickoff, teams) for event, kickoff, teams in
                     prematch_fixtures(board_raw, board_at, day, competition, LIVE_WINDOW)}
        for record in report["records"]:
            event = record["event_id"]
            target = targets.get(event)
            if target is None:
                issues.append({"event_id": event, "reason": "OUTSIDE_ARCHIVED_RESEARCH_SCOPE"})
                continue
            kickoff = utc(target["kickoff_at"])
            source = record["source"]
            raw, captured = cache._load(source, f"{ESPN}/{competition}/summary?event={event}")
            if (league != target["league"] or qualified.get(event) != (kickoff, target["team_ids"])
                    or not kickoff - LIVE_WINDOW <= min(board_at, captured)
                    <= max(board_at, captured) < cutoff < kickoff):
                issues.append({"event_id": event, "reason": "IDENTITY_OR_LIVE_TIME_MISMATCH"})
                continue
            payload = json.loads(raw)
            values = summary(raw, captured, event, kickoff, target["team_ids"])
            board_event = events[event]
            quotes, attempts = market_quote_chain(
                board_event["competitions"][0].get("odds") or board_event.get("odds"),
                board, payload, source, kickoff.isoformat(), as_of=cutoff)
            odds = [quote for quote in quotes if check_odds(quote, cutoff.isoformat())["status"] == "VERIFIED_INPUT"]
            try:
                load = observed_load({"lastFiveGames": payload.get("lastFiveGames") or []},
                                     target["team_ids"].values(), captured, kickoff)
            except (ValueError, KeyError, TypeError, AttributeError):
                load = {}
            rows.append({"fixture": target, "board_source": board, "summary_source": source,
                         "observed_fields": values, "quotes": odds, "quote_attempts": attempts,
                         "player_roster_entries_observed": sum(
                             len(block.get("roster") or []) for block in payload.get("rosters") or []),
                         "recent_schedule_observations": load,
                         "important_absences": "UNVERIFIED", "rotation": "UNVERIFIED",
                         "context_status": "BLOCKED", "ex_final_allowed": False})
    return rows, issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", type=Path, action="append", required=True)
    parser.add_argument("--targets", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixtures = [r["fixture"] for path in args.targets for r in json.loads(path.read_bytes())]
    targets = {row["event_id"]: row for row in fixtures}
    if len(targets) != len(fixtures):
        raise ValueError("Duplicate target events")
    cutoff = dt.datetime.now(dt.timezone.utc)
    rows, issues = [], []
    for path in args.capture:
        manifest = json.loads(path.read_bytes())
        result, errors = review_capture(manifest, HistoryArchive(path.parent / "cache", 0), targets, cutoff)
        rows.extend(result)
        issues.extend(errors)
    counts = Counter(row["fixture"]["date"] for row in rows)
    atomic_write(args.output, (json.dumps({"cutoff": cutoff.isoformat(), "fixtures": rows, "issues": issues,
                  "fixtures_by_date": counts, "quotes_by_market": Counter(q["market"] for row in rows for q in row["quotes"]),
                  "production_allowed": False}, ensure_ascii=False, indent=2) + "\n").encode())


if __name__ == "__main__":
    main()
