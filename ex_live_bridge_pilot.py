"""Read-only historical two-source live pilot. Never certifies EX FINAL."""
import argparse
import datetime as dt
import json
from pathlib import Path

from ex_espn_football_data_bridge import fetch_and_compare_historical_day


def run_pilot(league, season, day, as_of):
    result = fetch_and_compare_historical_day(league, season, day, as_of)
    comparison = result.get("comparison") or {}
    return {
        "league": league, "season": season, "day": day, "as_of": as_of,
        "status": result["status"], "issues": result["issues"],
        "matched": comparison.get("matched", 0),
        "unmatched": comparison.get("unmatched", 0),
        "ambiguous": comparison.get("ambiguous", 0),
        "conflicts": comparison.get("conflicts", []),
        "provenance": result.get("provenance", {}),
        "independent_sources_confirmed": False,
        "calibration_certified": False, "ex_final_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league", default="en.1")
    parser.add_argument("--season", default="2026-2027")
    parser.add_argument("--day", default="2026-11-01")
    parser.add_argument("--as-of", default=dt.date.today().isoformat())
    parser.add_argument("--out", default="ex_live_bridge_audit.json")
    args = parser.parse_args()
    report = run_pilot(args.league, args.season, args.day, args.as_of)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "issues", "matched", "unmatched", "ambiguous", "ex_final_allowed")}, ensure_ascii=False))
    return 0 if report["status"] != "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
