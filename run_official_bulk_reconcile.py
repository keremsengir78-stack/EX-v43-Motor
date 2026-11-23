"""Bulk reconcile official match-result evidence across all 75 candidate fixtures.

Input CSV: source_index,league,date,home,away,home_goals,away_goals,
           official_source_url,source_provider,evidence_reviewed
A reviewer flag and official-looking URL are not remote content verification.
This program records provisional score matches only and never certifies them.
"""
import argparse
import csv
import json
from pathlib import Path
from urllib.parse import urlparse

OFFICIAL_HOSTS = {
    "en.1": {"premierleague.com", "www.premierleague.com"},
    "es.1": {"laliga.com", "www.laliga.com"},
    "it.1": {"legaseriea.it", "www.legaseriea.it"},
}
FIELDS = ("source_index", "league", "date", "home", "away",
          "home_goals", "away_goals", "official_source_url",
          "source_provider", "evidence_reviewed")


def reconcile(queue, batches, evidence_rows):
    index = {x["index"]: x for x in queue["fixtures"]}
    if len(index) != 75 or len(batches) != 3:
        raise ValueError("Expected exactly 75 candidates in three batches")
    by_index = {}
    for batch in batches:
        for item in batch["records"]:
            idx = item["source_index"]
            if idx in by_index or idx not in index:
                raise ValueError("Invalid or repeated batch index")
            by_index[idx] = item
    if set(index) != set(by_index):
        raise ValueError("Missing candidate records")
    seen = set()
    accepted, rejected, conflicts = [], [], []
    for row in evidence_rows:
        try:
            idx = int(row["source_index"])
        except (ValueError, TypeError, KeyError):
            rejected.append({"source_index": row.get("source_index"), "reason": "INVALID_INDEX"})
            continue
        if idx in seen:
            rejected.append({"source_index": idx, "reason": "DUPLICATE_EVIDENCE"})
            continue
        seen.add(idx)
        if idx not in index:
            rejected.append({"source_index": idx, "reason": "UNKNOWN_INDEX"})
            continue
        candidate = index[idx]
        if any(row.get(k) != candidate[k] for k in ("league", "date", "home", "away")):
            rejected.append({"source_index": idx, "reason": "FIXTURE_IDENTITY_MISMATCH"})
            continue
        url = row.get("official_source_url", "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in OFFICIAL_HOSTS[candidate["league"]]:
            rejected.append({"source_index": idx, "reason": "NON_OFFICIAL_SOURCE_HOST"})
            continue
        if str(row.get("evidence_reviewed", "")).lower() != "true":
            rejected.append({"source_index": idx, "reason": "EVIDENCE_NOT_REVIEWED"})
            continue
        try:
            score = [int(row["home_goals"]), int(row["away_goals"])]
        except (ValueError, TypeError, KeyError):
            rejected.append({"source_index": idx, "reason": "INVALID_SCORE"})
            continue
        if min(score) < 0:
            rejected.append({"source_index": idx, "reason": "NEGATIVE_SCORE"})
            continue
        if score != candidate["reference_score"]:
            conflicts.append({"source_index": idx, "official_score": score,
                              "reference_score": candidate["reference_score"]})
            continue
        item = by_index[idx]
        item["reviewed_candidate_score"] = score
        item["reviewed_candidate_source_url"] = url
        item["official_verified"] = False
        item["official_score"] = None
        item["official_source_url"] = None
        item["review_status"] = "REVIEWER_ASSERTED_SCORE_MATCH_REMOTE_CONTENT_UNVERIFIED"
        accepted.append(idx)
    for batch in batches:
        batch["official_verified_count"] = sum(x["official_verified"] for x in batch["records"])
        batch["remaining_count"] = 25 - batch["official_verified_count"]
        batch["ex_final_allowed"] = False
    return {"provisional_match_indices": accepted, "accepted_indices": [],
            "rejected": rejected, "score_conflicts": conflicts,
            "official_verified_total": sum(b["official_verified_count"] for b in batches),
            "remaining": 75 - sum(b["official_verified_count"] for b in batches),
            "source_independence_certified": False,
            "remote_content_verified_by_reconciler": False, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent / "reports"
    queue = json.loads((root / "external_2627_combined_75_candidate_queue.json").read_text())
    batches = [json.loads((root / ("official_verification_batch_%02d.json" % n)).read_text())
               for n in (1, 2, 3)]
    with args.evidence.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError("Missing required evidence CSV columns")
        result = reconcile(queue, batches, list(reader))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for n, batch in enumerate(batches, 1):
        (args.output_dir / ("official_verification_batch_%02d.json" % n)).write_text(
            json.dumps(batch, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.output_dir / "official_bulk_reconcile_result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    if result["score_conflicts"] or result["rejected"]:
        raise SystemExit("Unresolved official evidence; inspect report before approval")


if __name__ == "__main__":
    main()
