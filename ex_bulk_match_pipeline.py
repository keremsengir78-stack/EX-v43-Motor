"""Bulk EX v4.3 evidence pipeline: isolate fixture failures and aggregate blockers.

Consumes reviewed input records, not live data. Never issues EX FINAL.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from ex_match_pipeline import process_match_evidence


REQUIRED = ("fixture_id", "market", "records", "venue", "season",
            "previous_season", "feature_scores", "as_of", "source_observations")


def run_batch(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
        raise ValueError("Expected object with matches array")
    matches = payload["matches"]
    if not matches:
        raise ValueError("No matches provided")
    if len(matches) > 500:
        raise ValueError("Maximum 500 matches per batch")
    ids, results, blockers = set(), [], Counter()
    for i, item in enumerate(matches):
        if not isinstance(item, dict):
            raise ValueError("Match %d is not an object" % i)
        fixture_id = item.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id.strip() or fixture_id in ids:
            raise ValueError("Missing or duplicate fixture ID")
        ids.add(fixture_id)
        missing = [key for key in REQUIRED if key not in item]
        if missing:
            result = {"status": "BLOCKED", "issues": ["input:missing:" + key for key in missing]}
        else:
            try:
                result = process_match_evidence(
                    item["market"], item["records"], item["venue"], item["season"],
                    item["previous_season"], item["feature_scores"], item["as_of"],
                    item["source_observations"])
            except (ValueError, KeyError, TypeError, IndexError, AttributeError) as exc:
                result = {"status": "BLOCKED", "issues": ["pipeline:invalid_input:" + type(exc).__name__]}
        status = result.get("status", "BLOCKED")
        if status not in ("BLOCKED", "EVIDENCE_READY_UNCALIBRATED"):
            raise ValueError("Unexpected pipeline status")
        issues = result.get("issues", [])
        if not isinstance(issues, list):
            raise ValueError("Invalid pipeline issue list")
        for issue in issues:
            blockers[str(issue).split(":")[0]] += 1
        results.append({"fixture_id": fixture_id, "market": item.get("market"),
                        "status": status, "issues": issues,
                        "calibrated_probability": None, "ex_final_allowed": False})
    return {"processed": len(results), "evidence_ready_uncalibrated":
            sum(r["status"] == "EVIDENCE_READY_UNCALIBRATED" for r in results),
            "blocked": sum(r["status"] == "BLOCKED" for r in results),
            "blocker_categories": dict(blockers), "results": results,
            "ex_final_allowed": False, "source_type": "REVIEWED_INPUT_ONLY_NO_LIVE_FETCH"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_batch(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
