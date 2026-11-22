"""Multi-date, multi-league historical provider audit. Never unlocks EX FINAL."""
import argparse
import datetime as dt
import json
from pathlib import Path

from ex_live_bridge_pilot import run_pilot

DEFAULT_CASES = (
    ("en.1", "2026-2027", "2026-11-01"),
    ("en.1", "2026-2027", "2026-10-25"),
    ("en.1", "2026-2027", "2026-10-18"),
    ("en.1", "2026-2027", "2026-10-04"),
    ("en.1", "2026-2027", "2026-09-20"),
    ("de.1", "2026-2027", "2026-11-07"),
    ("de.1", "2026-2027", "2026-10-31"),
    ("de.1", "2026-2027", "2026-10-24"),
    ("de.1", "2026-2027", "2026-10-17"),
    ("de.1", "2026-2027", "2026-10-03"),
    ("es.1", "2026-2027", "2026-11-08"),
    ("es.1", "2026-2027", "2026-11-01"),
    ("es.1", "2026-2027", "2026-10-25"),
    ("es.1", "2026-2027", "2026-10-18"),
    ("es.1", "2026-2027", "2026-10-04"),
    ("it.1", "2026-2027", "2026-11-08"),
    ("it.1", "2026-2027", "2026-11-01"),
    ("it.1", "2026-2027", "2026-10-25"),
    ("it.1", "2026-2027", "2026-10-18"),
    ("it.1", "2026-2027", "2026-10-04"),
)


REVIEWED_ALIASES = {
    "it.1": {"acmilan": "Milan", "internazionale": "Inter"},
    "en.1": {"newcastleunited": "Newcastle", "hullcity": "Hull",
             "brightonhovealbion": "Brighton",
             "manchesterunited": "Man United", "bournemouth": "Bournemouth",
             "leedsunited": "Leeds"},
    "es.1": {"realbetis": "Betis", "celtavigo": "Celta",
             "atleticomadrid": "Ath Madrid"},
    "de.1": {"vfbstuttgart": "Stuttgart"},
}


def run_batch(as_of, cases=DEFAULT_CASES, reviewed_aliases=False):
    reports = []
    for league, season, day in cases:
        if reviewed_aliases and league in REVIEWED_ALIASES:
            reports.append(run_pilot(league, season, day, as_of, alias=REVIEWED_ALIASES))
        else:
            reports.append(run_pilot(league, season, day, as_of))
    matched = sum(report["matched"] for report in reports)
    unmatched = sum(report["unmatched"] for report in reports)
    ambiguous = sum(report["ambiguous"] for report in reports)
    conflicts = sum(report["conflict_count"] for report in reports)
    blocked = sum(report["status"] == "BLOCKED" for report in reports)
    partial = sum(report["status"] == "PARTIAL_PROVISIONAL_MATCH" for report in reports)
    score_conflict_cases = sum(report["status"] == "SCORE_CONFLICT" for report in reports)
    alias_review = sum(report.get("alias_suggestion_count", 0) for report in reports)
    complete = sum(report["status"] == "PROVISIONAL_MATCH_UNAUDITED" for report in reports)
    return {
        "as_of": as_of, "case_count": len(reports),
        "reviewed_aliases_enabled": reviewed_aliases,
        "alias_mapping_scope": sorted(REVIEWED_ALIASES) if reviewed_aliases else [],
        "completed_provisional_cases": complete, "blocked_cases": blocked,
        "partial_cases": partial, "score_conflict_cases": score_conflict_cases,
        "alias_review_required": alias_review,
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
    parser.add_argument("--reviewed-aliases", action="store_true")
    args = parser.parse_args()
    report = run_batch(args.as_of, reviewed_aliases=args.reviewed_aliases)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in ("status", "case_count", "matched", "unmatched", "ambiguous", "conflict_count", "blocked_cases", "ex_final_allowed")}, ensure_ascii=False))
    return 0 if report["status"] == "PROVISIONAL_MULTI_CASE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
