"""Audit evidence provenance without mistaking score agreement for source independence."""
import json
from pathlib import Path
from urllib.parse import urlparse

def audit(queue, batches, broadcaster):
    candidates = {x["index"]: x for x in queue["fixtures"]}
    official, broadcast, issues = set(), set(), []
    if len(candidates) != 75:
        raise ValueError("Candidate scope must be 75")
    for batch in batches:
        for x in batch["records"]:
            idx = x["source_index"]
            if x.get("official_verified"):
                if idx in official:
                    raise ValueError("Duplicate official evidence")
                official.add(idx)
                u = urlparse(x.get("official_source_url") or "")
                expected = {"es.1": ("laliga.com", "www.laliga.com"),
                            "it.1": ("legaseriea.it", "www.legaseriea.it"),
                            "en.1": ("premierleague.com", "www.premierleague.com")}
                if u.scheme != "https" or u.hostname not in expected[x["league"]]:
                    issues.append({"index": idx, "reason": "NOT_PRIMARY_LEAGUE_DOMAIN"})
                if x.get("official_score") != candidates[idx]["reference_score"]:
                    issues.append({"index": idx, "reason": "PRIMARY_SCORE_CONFLICT"})
                # Generic schedule and matchweek pages cannot alone prove a particular
                # fixture was present; exact fixture evidence needs an auditable locator.
                if "/schedule" in u.path or "/results/" in u.path:
                    issues.append({"index": idx, "reason": "PAGE_LEVEL_EVIDENCE_NO_EXACT_MATCH_LOCATOR"})
    for x in broadcaster["records"]:
        idx = x["source_index"]
        if idx in broadcast or idx not in candidates:
            raise ValueError("Invalid broadcaster index")
        broadcast.add(idx)
        if x.get("independent_broadcaster_match"):
            if x.get("independent_broadcaster_score") != candidates[idx]["reference_score"]:
                issues.append({"index": idx, "reason": "BROADCAST_SCORE_CONFLICT"})
            if not x.get("independent_score_evidence_excerpt") or not x.get("independent_score_evidence_locator"):
                raise ValueError("Unsupported broadcaster verification claim")
        else:
            issues.append({"index": idx, "reason": "BROADCAST_INDEPENDENT_EVIDENCE_PENDING"})
        if x.get("official_league_score_verified") is not False:
            issues.append({"index": idx, "reason": "BROADCAST_MISLABELED_OFFICIAL"})
    if official & broadcast:
        issues.append({"reason": "OVERLAPPING_OFFICIAL_BROADCAST_SCOPE"})
    if official | broadcast != set(candidates):
        issues.append({"reason": "INCOMPLETE_EVIDENCE_COVERAGE"})
    return {"candidate_count": len(candidates), "primary_league_domain_claims": len(official),
            "broadcaster_result_claims": len(broadcast),
            "exact_match_primary_evidence_certified_by_this_audit": 0,
            "upstream_source_lineage_independently_certified": False,
            "issues": issues, "ex_final_allowed": False}

def main():
    root = Path(__file__).resolve().parent / "reports"
    load = lambda name: json.loads((root / name).read_text(encoding="utf-8"))
    q = load("external_2627_combined_75_candidate_queue.json")
    b = [load("official_verification_batch_%02d.json" % n) for n in (1, 2, 3)]
    nbc = load("england_2627_nbc_broadcaster_37_crosscheck.json")
    result = audit(q, b, nbc)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    # Missing exact match anchors are review tasks, not authorization to finalize.
    if result["ex_final_allowed"] or result["upstream_source_lineage_independently_certified"]:
        raise SystemExit("Fail-closed evidence gate broken")

if __name__ == "__main__":
    main()
