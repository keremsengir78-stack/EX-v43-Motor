"""Measure observed EX evidence from existing archives without opening production gates."""

import argparse
from collections import Counter
import json
from pathlib import Path

from ex_leagues import APPROVED_LEAGUES
from ex_history_archive import atomic_write


def audit(plan, examples, captures):
    competitions = {entry[1]: code for code, entry in APPROVED_LEAGUES.items()}
    events = {row["event_id"]: competitions.get(row["competition"])
              for row in plan["pending_events"]}
    historical = {league: Counter() for league in APPROVED_LEAGUES}
    for league in events.values():
        if league:
            historical[league]["summary_plan_events"] += 1
    for row in examples:
        league = events.get(row["event_id"])
        if league:
            bucket = historical[league]
            bucket["retrospective_rows"] += 1
            for name in ("strength", "workload", "minutes"):
                bucket[name] += row.get(name) is not None

    observed = {league: Counter() for league in APPROVED_LEAGUES}
    seen, boards = set(), set()
    for capture in captures:
        for league, report in capture.get("reports", {}).items():
            if league not in observed:
                continue
            boards.add((league, capture["day"]))
            for row in report.get("records", []):
                key = league, row["event_id"]
                if key in seen:
                    continue
                seen.add(key)
                observed[league]["archived_fixtures"] += 1
                fields = row.get("observed_fields", {})
                observed[league]["roster_payloads"] += fields.get("roster_payload_observed") is True
                observed[league]["quote_payloads"] += fields.get("quote_payload_observed") is True
    return {"archived_plan_total": len(events), "retrospective_total": len(examples),
            "leagues": {code: {"published_boards_observed": sum(k[0] == code for k in boards),
                               "historical": dict(historical[code]), "prematch": dict(observed[code])}
                        for code in APPROVED_LEAGUES},
            "production_calibration_allowed": False, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--capture", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.plan.read_text()),
                   [json.loads(line) for line in args.examples.read_text().splitlines()],
                   [json.loads(path.read_text()) for path in args.capture])
    atomic_write(args.output, (json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result))


if __name__ == "__main__":
    main()
