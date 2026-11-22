"""Compare raw and opt-in alias audits without granting model certification."""
import argparse
import json
from pathlib import Path


def compare_audits(raw, reviewed):
    if raw.get("reviewed_aliases_enabled") is not False or reviewed.get("reviewed_aliases_enabled") is not True:
        raise ValueError("raw and reviewed audit modes are reversed")
    if raw.get("ex_final_allowed") is not False or reviewed.get("ex_final_allowed") is not False:
        raise ValueError("unexpected EX FINAL certification in provisional audit")
    if raw.get("as_of") != reviewed.get("as_of"):
        raise ValueError("audit cutoffs differ")
    for record in (raw, reviewed):
        if record.get("independent_sources_confirmed") is not False or record.get("calibration_certified") is not False:
            raise ValueError("unverified provider comparison claims independent validation")
    raw_cases = raw.get("cases")
    reviewed_cases = reviewed.get("cases")
    if not isinstance(raw_cases, list) or not isinstance(reviewed_cases, list):
        raise ValueError("missing case lists")
    if len(raw_cases) != len(reviewed_cases) or not raw_cases:
        raise ValueError("case counts differ or empty")
    cases = []
    seen = set()
    for original, updated in zip(raw_cases, reviewed_cases):
        identity = ("league", "season", "day", "as_of")
        if any(original.get(key) != updated.get(key) for key in identity):
            raise ValueError("audit cases not aligned")
        case_id = tuple(original.get(key) for key in identity)
        if case_id in seen:
            raise ValueError("duplicate audit case")
        seen.add(case_id)
        for record in (original, updated):
            for field in ("matched", "unmatched", "conflict_count"):
                if type(record.get(field)) is not int or record[field] < 0:
                    raise ValueError("invalid audit counts")
        if any(record.get("ex_final_allowed") is not False for record in (original, updated)):
            raise ValueError("case unexpectedly certifies EX FINAL")
        if original["matched"] + original["unmatched"] != updated["matched"] + updated["unmatched"]:
            raise ValueError("different fixture populations cannot be compared")
        cases.append({
            "league": original["league"], "day": original["day"],
            "raw_matched": original["matched"], "reviewed_matched": updated["matched"],
            "matched_delta": updated["matched"] - original["matched"],
            "raw_unmatched": original["unmatched"], "reviewed_unmatched": updated["unmatched"],
            "unmatched_delta": updated["unmatched"] - original["unmatched"],
            "raw_conflicts": original["conflict_count"],
            "reviewed_conflicts": updated["conflict_count"],
            "new_conflicts": max(0, updated["conflict_count"] - original["conflict_count"]),
            "unresolved_fixtures": updated.get("unmatched_details", []),
            "review_candidates": updated.get("alias_suggestions", []),
            "unresolved_reason": "NAME_OR_FIXTURE_MISMATCH_REQUIRES_SOURCE_REVIEW" if updated["unmatched"] else "NONE",
        })
    raw_matched = sum(case["raw_matched"] for case in cases)
    reviewed_matched = sum(case["reviewed_matched"] for case in cases)
    raw_unmatched = sum(case["raw_unmatched"] for case in cases)
    reviewed_unmatched = sum(case["reviewed_unmatched"] for case in cases)
    regressions = [case for case in cases if case["matched_delta"] < 0 or case["new_conflicts"] > 0]
    remaining_by_league = {}
    for case in cases:
        remaining_by_league[case["league"]] = remaining_by_league.get(case["league"], 0) + case["reviewed_unmatched"]
    remaining_by_league = dict(sorted(remaining_by_league.items(), key=lambda pair: (-pair[1], pair[0])))
    return {
        "status": "REGRESSION_DETECTED" if regressions else "PROVISIONAL_COMPARISON",
        "as_of": raw["as_of"], "case_count": len(cases),
        "raw_matched": raw_matched, "reviewed_matched": reviewed_matched,
        "matched_delta": reviewed_matched - raw_matched,
        "raw_unmatched": raw_unmatched, "reviewed_unmatched": reviewed_unmatched,
        "coverage_raw": raw_matched / (raw_matched + raw_unmatched) if raw_matched + raw_unmatched else 0,
        "coverage_reviewed": reviewed_matched / (reviewed_matched + reviewed_unmatched) if reviewed_matched + reviewed_unmatched else 0,
        "coverage_gain_percentage_points": round(100 * (reviewed_matched / (reviewed_matched + reviewed_unmatched) - raw_matched / (raw_matched + raw_unmatched)), 2) if raw_matched + raw_unmatched and reviewed_matched + reviewed_unmatched else 0,
        "regression_count": len(regressions), "cases": cases,
        "remaining_by_league": remaining_by_league,
        "cases_with_unresolved": sum(case["reviewed_unmatched"] > 0 for case in cases),
        "review_queue": [
            {"league": case["league"], "day": case["day"],
             "unmatched": case["reviewed_unmatched"],
             "fixtures": case["unresolved_fixtures"]}
            for case in sorted(cases, key=lambda item: (-item["reviewed_unmatched"], item["league"], item["day"]))
            if case["reviewed_unmatched"]
        ],
        "data_gate": "BLOCKED_UNRESOLVED_FIXTURES" if reviewed_unmatched else "PROVISIONAL_COVERAGE_ONLY",
        "technical_gate": "FAILED_REGRESSION" if regressions else "PASSED_AUDIT_COMPARISON",
        "independent_sources_confirmed": False,
        "sample_sufficiency_certified": False,
        "calibration_certified": False, "ex_final_allowed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--reviewed", required=True)
    parser.add_argument("--out", default="ex_live_bridge_delta_audit.json")
    args = parser.parse_args()
    report = compare_audits(json.loads(Path(args.raw).read_text()),
                            json.loads(Path(args.reviewed).read_text()))
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("status", "raw_matched", "reviewed_matched", "matched_delta",
                       "reviewed_unmatched", "regression_count", "ex_final_allowed")}))
    return 2 if report["regression_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
