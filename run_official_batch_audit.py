"""Audit official-source batches without upgrading unsupported score evidence.

The checker validates metadata, uniqueness, source provenance and fail-closed gates.
A passing audit is NOT independent verification of the remote page content.
"""
import json
from pathlib import Path


def audit(queue, batches):
    expected = {x["index"]: x for x in queue["fixtures"]}
    if len(expected) != 75 or len(batches) != 3:
        raise ValueError("Incorrect candidate scope")
    seen = set()
    confirmed = 0
    suspicious = []
    for number, batch in enumerate(batches, 1):
        if batch.get("batch") != number or len(batch["records"]) != 25:
            raise ValueError("Batch number/count mismatch")
        if batch.get("ex_final_allowed") is not False:
            raise ValueError("EX FINAL must remain locked")
        actual_confirmed = 0
        for item in batch["records"]:
            idx = item["source_index"]
            if idx in seen or idx not in expected:
                raise ValueError("Duplicate or unexpected candidate")
            seen.add(idx)
            source = expected[idx]
            for field in ("league", "date", "home", "away"):
                if item[field] != source[field]:
                    raise ValueError("Fixture mismatch: " + field)
            if item["score"] != source["reference_score"]:
                raise ValueError("Score mismatch")
            if item.get("official_verified"):
                actual_confirmed += 1
                if item.get("official_score") != item["score"]:
                    raise ValueError("Official score disagreement")
                url = item.get("official_source_url")
                if not isinstance(url, str) or not url.startswith("https://"):
                    raise ValueError("Official verification lacks HTTPS provenance")
                if "laliga.com" in url and "gameweek-1" in url and item["date"] > "2026-08-24":
                    suspicious.append({"source_index": idx,
                                       "reason": "GAMEWEEK_1_URL_USED_FOR_LATER_DATE",
                                       "date": item["date"], "source_url": url})
            else:
                if item.get("official_score") is not None or item.get("official_source_url") is not None:
                    raise ValueError("Unverified item has official evidence")
        if batch.get("official_verified_count") != actual_confirmed:
            raise ValueError("Batch verification count mismatch")
        confirmed += actual_confirmed
    if seen != set(expected):
        raise ValueError("Missing candidates")
    return {"candidate_count": 75, "claimed_official_verified": confirmed,
            "suspicious_source_scope": suspicious,
            "independently_verified_by_audit": 0,
            "ex_final_allowed": False}


def main():
    root = Path(__file__).resolve().parent / "reports"
    queue = json.loads((root / "external_2627_combined_75_candidate_queue.json").read_text(encoding="utf-8"))
    batches = [json.loads((root / ("official_verification_batch_%02d.json" % i)).read_text(encoding="utf-8"))
               for i in (1, 2, 3)]
    result = audit(queue, batches)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result["suspicious_source_scope"]:
        raise SystemExit("Official source date/week scope audit failed")


if __name__ == "__main__":
    main()
