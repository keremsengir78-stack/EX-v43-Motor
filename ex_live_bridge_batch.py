"""Multi-date, multi-league historical provider audit. Never unlocks EX FINAL."""
import argparse
import datetime as dt
import json
from pathlib import Path

from ex_live_bridge_pilot import run_pilot

DEFAULT_CASES = (
    ("en.1", "2026-2027", "2026-11-01"),
    ("en.1", "2026-2027", "2026-10-25"),
    ("de.1", "2026-2027", "2026-11-07"),
    ("es.1", "2026-2027", "2026-11-08"),
    ("it.1", "2026-2027", "2026-11-08"),
)


def run_batch(as_of, cases=DEFAULT_CASES):
    reports = []
    for league, season, day in cases:
        reports.append(run_pilot(league, season, day, as_of))
    matched = sum(report["matched"] for report in reports)
    unmatched = sum(report["unmatched"] for report in reports)
    ambiguous = sum(report["ambiguous"] for report in reports)
    conflicts = sum(report["conflict_count"] for report in reports)
    blocked = sum(report["status"] == "BLOCKED" for report in reports)
    complete = sum(report["status"] == "PROVISIONAL_MATCH_UNAUDITED" for report in reports)
    return {
        "as_of": as_of, "case_count": len(reports),
        "completed_provisional_cases": complete, "blocked_cases": blocked,
        "matched": matched, "unmatched": unmatched,
        "ambiguous": ambiguous, "conflict_count": conflicts,
        "coverage": matched / (matched + unmatched) if matched + unmatched else 0.0,
        "cases": reports,
        "independent_sources_confirmed": False,
        "sample_sufficiency_certified": False,
        "calibration_certified": False,
        "ex_final_allowed": False,
        "status": "PROVISIONAL_MULTI_CASE" if complete == len(reports) and reports else "INCOMPLETE_OR_CONFLICTING",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=dt.date.today().isoformat())
    parser.add_argument("--out", default="ex_live_bridge_batch_audit.json")
    args = parser.parse_args()
    report = run_batch(args.as_of)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "case_count", "matched", "unmatched", "ambiguous", "conflict_count", "blocked_cases", "ex_final_allowed")}, ensure_ascii=False))
    return 0 if report["status"] == "PROVISIONAL_MULTI_CASE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
