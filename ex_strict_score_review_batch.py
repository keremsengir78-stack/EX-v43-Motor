"""Prepare bounded independent score review batches without certifying fixtures.

Strict team/date/score matches are candidates, not source-independent approvals.
"""


def build_review_batch(report, limit=100, offset=0):
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    if type(limit) is not int or not 1 <= limit <= 500:
        raise ValueError("limit must be between 1 and 500")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be nonnegative")
    total = report.get("total")
    confirmed = report.get("confirmed")
    remaining = report.get("remaining")
    rows = report.get("verified")
    if (any(type(x) is not int or x < 0 for x in (total, confirmed, remaining))
            or confirmed + remaining != total
            or not isinstance(rows, list) or len(rows) != confirmed):
        raise ValueError("strict report count mismatch")
    if offset > len(rows):
        raise ValueError("offset exceeds matched records")
    pending = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict) or not isinstance(row.get("fixture"), dict):
            raise ValueError("malformed fixture at %d" % i)
        fixture = row["fixture"]
        if fixture.get("independent_score_verified") is not False:
            raise ValueError("review input must remain explicitly unverified")
        if row.get("verification") != "EXACT_TEAM_DATE_SCORE_MATCH":
            raise ValueError("strict match missing")
        for field in ("league", "season", "date", "home", "away"):
            if not isinstance(fixture.get(field), str) or not fixture[field].strip():
                raise ValueError("missing fixture identifier: " + field)
        score = row.get("score")
        if (not isinstance(score, list) or len(score) != 2
                or any(type(x) is not int or x < 0 for x in score)):
            raise ValueError("invalid score")
        pending.append({
            "index": i, "league": fixture["league"], "season": fixture["season"],
            "date": fixture["date"], "home": fixture["home"], "away": fixture["away"],
            "matched_score": list(score),
            "secondary_provider": row.get("secondary_provider"),
            "secondary_url": row.get("secondary_url"),
            "review_status": "REQUIRES_INDEPENDENT_SCORE_EVIDENCE",
            "independent_score_verified": False,
        })
    return {
        "status": "REVIEW_REQUIRED", "source_total": total,
        "strict_matches": confirmed, "other_unmatched": remaining,
        "pending_independent_review": len(pending),
        "offset": offset, "exported": len(pending[offset:offset + limit]),
        "truncated": offset + limit < len(pending),
        "fixtures": pending[offset:offset + limit],
        "independent_score_verified": False, "ex_final_allowed": False,
    }
