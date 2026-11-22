"""Verify a published independent review queue against source diagnostics."""


def validate(queue, diagnostics):
    if queue.get("ex_final_allowed") is not False or queue.get("score_verified") is not False:
        raise ValueError("review queue must remain unverified")
    total=queue.get("total_review_queue")
    if type(total) is not int or total<0 or total!=diagnostics.get("unmatched_total"):
        raise ValueError("queue total differs from diagnostics")
    fixtures=queue.get("fixtures")
    if not isinstance(fixtures,list) or queue.get("exported")!=len(fixtures):
        raise ValueError("incorrect exported fixture count")
    if queue.get("truncated")!=(len(fixtures)<total):
        raise ValueError("incorrect truncation marker")
    if queue.get("queue_version")!=2:
        raise ValueError("unsupported review queue version")
    league_counts={k:v["count"] for k,v in diagnostics.get("by_league",{}).items()}
    if sum(league_counts.values())!=total:
        raise ValueError("diagnostic league totals disagree")
    if any(x.get("league") not in league_counts or x.get("review_status")!="REQUIRES_INDEPENDENT_SOURCE_REVIEW" for x in fixtures):
        raise ValueError("unexpected queue fixture")
    return {"total":total,"exported":len(fixtures),
            "by_league":league_counts,"score_verified":False,
            "ex_final_allowed":False}
