"""Audit historical prematch gaps without turning dated fixture evidence into forecasts."""

import argparse
import json
from pathlib import Path

from ex_cross_verify import norm
from ex_espn_provider import ESPN_LEAGUES
from ex_history_archive import HistoryArchive, atomic_write, utc
from ex_history_sources import ESPN
from run_ex_prematch_archive import summary
from run_ucl_baselines import FIXTURE_CONFIG, team_index, verified_bytes
from run_ucl_research import UEFA_SNAPSHOT, uefa_fixtures


def audit(report, caches):
    metadata = json.loads(UEFA_SNAPSHOT.with_suffix(".json").read_text())
    raw = verified_bytes(UEFA_SNAPSHOT.with_suffix(".html"), metadata["sha256"])
    config = json.loads(FIXTURE_CONFIG.read_text())
    _, aliases = team_index(config["domestic_team_names"])
    canonical = {value: team for (_, value), team in aliases.items()}
    uefa = {(kickoff, canonical.get(home, home), canonical.get(away, away))
            for kickoff, home, away in uefa_fixtures(raw, 5)}
    stores = [HistoryArchive(path, 0) for path in caches]
    now = utc(report["capture_window"]["measured_at"])
    results = []
    for event, state in report["fixture_capture_status"].items():
        if state != "PREMATCH_WINDOW_CLOSED_WITHOUT_EVIDENCE":
            continue
        fixture = report["fixtures"][event]
        kickoff = utc(fixture["kickoff"])
        names = fixture["names"]
        home, away = (canonical.get(norm(names[side]), norm(names[side])) for side in ("home", "away"))
        official = (fixture["league"] == "UCL" and utc(metadata["retrieved_at"]) < kickoff
                    and (kickoff, home, away) in uefa)
        url = f"{ESPN}/{ESPN_LEAGUES[fixture['league']]}/summary?event={event}"
        found = None
        for store in stores:
            located = store.prior_capture(url, kickoff)
            if located:
                content, stamp, source = located
                summary(content, stamp, event, kickoff, fixture["teams"])
                found = source
                break
        results.append({"event_id": event, **fixture, "summary": found,
                        "fixture_evidence": metadata if official else None,
                        "status": "DATED_SUMMARY_FOUND" if found else
                        "DATED_FIXTURE_ONLY" if official else "NO_DATED_PREMATCH_EVIDENCE",
                        "forecast_recovered": False})
    return {"inventory_measured_at": now.isoformat(), "searched_archives": len(stores),
            "fixtures": results, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--cache", type=Path, action="append", default=[])
    parser.add_argument("--packs", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.packs:
        args.cache.extend(path for path in args.packs.glob("*/pregame-cache") if path.is_dir())
    report = audit(json.loads(args.inventory.read_text()), args.cache)
    atomic_write(args.output, json.dumps(report, indent=2).encode())
    from collections import Counter
    print(json.dumps(Counter(row["status"] for row in report["fixtures"])))


if __name__ == "__main__":
    main()
