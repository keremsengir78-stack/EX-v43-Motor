"""Fail-closed integrity audit of the 75 external score candidates.

This checks the local queue against the original reconciliation. It does NOT
independently verify match results or certify external source lineage.
"""
import json
from collections import Counter
from pathlib import Path


def audit(source, queue):
    original = source["verified"]
    rows = queue["fixtures"]
    if len(rows) != 75 or queue["candidate_count"] != 75:
        raise ValueError("Candidate queue count mismatch")
    if queue.get("independent_score_verified") is not False or queue.get("ex_final_allowed") is not False:
        raise ValueError("Fail-closed gates must remain false")
    expected_leagues = {"en.1": 37, "es.1": 31, "it.1": 7}
    counts = Counter()
    seen = set()
    for row in rows:
        index = row["index"]
        if not isinstance(index, int) or not 0 <= index < len(original) or index in seen:
            raise ValueError("Invalid or duplicated original index")
        seen.add(index)
        fixture = original[index]["fixture"]
        for key in ("league", "date", "home", "away"):
            if row[key] != fixture[key]:
                raise ValueError("Fixture identity mismatch: " + key)
        if row["reference_score"] != original[index]["score"]:
            raise ValueError("Original score mismatch")
        if row["other_score"] != row["reference_score"]:
            raise ValueError("External score conflict")
        if row["status"] != "SCORE_MATCH_CANDIDATE":
            raise ValueError("Unexpected candidate status")
        if row["provider"] != "fixturedl":
            raise ValueError("Unexpected provider")
        if not row["source_url"].startswith("https://github.com/oladeeayo/open-matchday/blob/master/data/"):
            raise ValueError("External provenance URL mismatch")
        if fixture["season"] != "2026-27":
            raise ValueError("Unexpected season")
        counts[row["league"]] += 1
    if dict(counts) != expected_leagues or queue["by_league"] != expected_leagues:
        raise ValueError("League distribution mismatch")
    return {"candidate_count": len(rows), "by_league": dict(counts),
            "independent_verified_by_this_audit": 0, "ex_final_allowed": False}


def main():
    root = Path(__file__).resolve().parent
    source = json.loads((root / "reports/latest_multileague_strict_score_reconcile.json").read_text(encoding="utf-8"))
    queue = json.loads((root / "reports/external_2627_combined_75_candidate_queue.json").read_text(encoding="utf-8"))
    print(json.dumps(audit(source, queue), sort_keys=True))


if __name__ == "__main__":
    main()
