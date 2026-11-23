"""Single-pass, machine-readable EX readiness report for the 75-record evidence scope.

Claims are NOT certified solely because an official-looking URL is present.
"""
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


def build_report(queue, batches, broadcaster):
    candidates = {x["index"]: x for x in queue["fixtures"]}
    if len(candidates) != 75 or len(batches) != 3:
        raise ValueError("Expected 75 unique candidates and 3 batches")
    items = {}
    for batch in batches:
        if len(batch["records"]) != 25:
            raise ValueError("Each batch must contain 25 records")
        for row in batch["records"]:
            idx = row["source_index"]
            if idx in items or idx not in candidates:
                raise ValueError("Duplicate or unknown fixture")
            items[idx] = row
    if set(items) != set(candidates):
        raise ValueError("Incomplete batch coverage")
    nbc = {r["source_index"]: r for r in broadcaster["records"]}
    if len(nbc) != len(broadcaster["records"]):
        raise ValueError("Duplicate broadcaster evidence")
    status = Counter()
    review = []
    for idx, original in sorted(candidates.items()):
        item = items[idx]
        if any(item.get(field) != original[field] for field in ("league", "date", "home", "away")):
            raise ValueError("Fixture mismatch")
        if item["score"] != original["reference_score"]:
            raise ValueError("Candidate score mismatch")
        if item.get("official_verified"):
            if item.get("official_score") != item["score"]:
                raise ValueError("Official score mismatch")
            url = item.get("official_source_url") or ""
            path = urlparse(url).path.lower()
            # A team schedule or a general results page has no exact-match
            # anchor: it cannot certify the particular fixture on its own.
            generic = "/schedule" in path or "/results/" in path
            if generic:
                status["official_page_level_claims_pending_exact_fixture_proof"] += 1
                review.append({"index": idx, "reason": "EXACT_MATCH_EVIDENCE_MISSING"})
            else:
                status["official_link_claims_needing_content_review"] += 1
                review.append({"index": idx, "reason": "CONTENT_NOT_MACHINE_VERIFIED"})
        elif idx in nbc:
            status["broadcaster_claims_pending_independent_content_review"] += 1
            review.append({"index": idx, "reason": "BROADCASTER_NOT_OFFICIAL"})
        else:
            status["no_claim"] += 1
            review.append({"index": idx, "reason": "NO_EVIDENCE"})
    return {
        "scope": "75 historical 2026-27 score candidates, NOT full EX engine readiness",
        "candidate_count": 75, "classification": dict(status),
        "automatically_certified_exact_match_results": 0,
        "upstream_independence_certified": False,
        "open_review_count": len(review),
        "review_queue": review,
        "ex_final_allowed": False,
    }


def main():
    root = Path(__file__).resolve().parent / "reports"
    read = lambda name: json.loads((root / name).read_text(encoding="utf-8"))
    result = build_report(
        read("external_2627_combined_75_candidate_queue.json"),
        [read("official_verification_batch_%02d.json" % i) for i in (1, 2, 3)],
        read("england_2627_nbc_broadcaster_37_crosscheck.json"),
    )
    print(json.dumps({k: v for k, v in result.items() if k != "review_queue"}, sort_keys=True))
    if result["ex_final_allowed"] or result["open_review_count"] != 75:
        raise SystemExit("Fail-closed review invariant violated")


if __name__ == "__main__":
    main()
