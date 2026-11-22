"""Evaluate historical pilot coverage and calibration readiness without certifying model gates."""
import argparse
import json
from pathlib import Path


def sample_readiness(audit, minimum_matches_per_league=30, minimum_days_per_league=5):
    if audit.get("ex_final_allowed") is not False or audit.get("technical_gate") != "PASSED_AUDIT_COMPARISON":
        raise ValueError("untrusted provisional audit")
    if type(minimum_matches_per_league) is not int or minimum_matches_per_league < 1:
        raise ValueError("invalid match threshold")
    if type(minimum_days_per_league) is not int or minimum_days_per_league < 1:
        raise ValueError("invalid day threshold")
    cases = audit.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("missing cases")
    leagues = {}
    seen = set()
    for case in cases:
        if any(type(case.get(k)) is not int or case[k] < 0 for k in
               ("reviewed_matched", "reviewed_unmatched", "reviewed_conflicts")):
            raise ValueError("invalid case counts")
        key = (case["league"], case["day"])
        if key in seen:
            raise ValueError("duplicate league-day")
        seen.add(key)
        row = leagues.setdefault(case["league"], {"days": 0, "matched": 0,
                                                  "unmatched": 0, "conflicts": 0})
        row["days"] += 1
        row["matched"] += case["reviewed_matched"]
        row["unmatched"] += case["reviewed_unmatched"]
        row["conflicts"] += case["reviewed_conflicts"]
    for league, row in leagues.items():
        row["meets_diagnostic_floor"] = (
            row["days"] >= minimum_days_per_league
            and row["matched"] >= minimum_matches_per_league
            and row["unmatched"] == 0 and row["conflicts"] == 0)
        row["additional_days_needed"] = max(0, minimum_days_per_league - row["days"])
        row["additional_matches_needed"] = max(0, minimum_matches_per_league - row["matched"])
    return {
        "status": "DIAGNOSTIC_SAMPLE_FLOOR_ONLY",
        "thresholds": {"minimum_matches_per_league": minimum_matches_per_league,
                       "minimum_days_per_league": minimum_days_per_league},
        "leagues": dict(sorted(leagues.items())),
        "all_leagues_meet_diagnostic_floor": all(row["meets_diagnostic_floor"] for row in leagues.values()),
        "sample_sufficiency_certified": False,
        "calibration_certified": False,
        "independent_sources_confirmed": False,
        "ex_final_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True)
    parser.add_argument("--out", default="ex_sample_readiness_audit.json")
    args = parser.parse_args()
    report = sample_readiness(json.loads(Path(args.audit).read_text()))
    Path(args.out).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
