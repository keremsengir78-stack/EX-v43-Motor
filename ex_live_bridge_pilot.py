"""Read-only historical two-source live pilot. Never certifies EX FINAL."""
import argparse
import datetime as dt
import json
from pathlib import Path

from ex_espn_football_data_bridge import fetch_and_compare_historical_day


def run_pilot(league, season, day, as_of):
    try:
        result = fetch_and_compare_historical_day(league, season, day, as_of)
    except Exception as exc:
        result = {"status": "BLOCKED", "issues": ["pilot:unexpected_error:" + type(exc).__name__],
                  "comparison": None, "provenance": {}}
    comparison = result.get("comparison") or {}
    return {
        "league": league, "season": season, "day": day, "as_of": as_of,
        "status": result["status"], "issues": result["issues"],
        "matched": comparison.get("matched", 0),
        "unmatched": comparison.get("unmatched", 0),
        "ambiguous": comparison.get("ambiguous", 0),
        "conflicts": comparison.get("conflicts", []),
        "conflict_count": len(comparison.get("conflicts", [])),
        "alias_suggestion_count": comparison.get("alias_suggestion_count", 0),
        "coverage": comparison.get("coverage", 0),
        "source_agreement_status": comparison.get("status", "NOT_CHECKED"),
        "sample_size": comparison.get("matched", 0) + comparison.get("unmatched", 0),
        "sample_sufficiency_certified": False,
        "sample_limitations": ["single_historical_day", "not_a_calibration_sample"],
        "unmatched_details": comparison.get("unmatched_details", []),
        "alias_suggestions": comparison.get("alias_suggestions", []),
        "diagnostic_summary": {
            "missing_or_ambiguous": comparison.get("unmatched", 0),
            "score_conflicts": len(comparison.get("conflicts", [])),
            "alias_review_required": comparison.get("alias_suggestion_count", 0),
            "provider_issues": result.get("issues", []),
        },
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
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "issues", "matched", "unmatched", "ambiguous", "ex_final_allowed")}, ensure_ascii=False))
    return 0 if report["status"] == "PROVISIONAL_MATCH_UNAUDITED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
