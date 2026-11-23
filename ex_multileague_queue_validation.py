"""Verify a published independent review queue against source diagnostics.

Validation is deliberately fail-closed. Counts from distinct scopes cannot be
silently combined or accepted when malformed.
"""


def _count(value, label):
    if type(value) is not int or value < 0:
        raise ValueError("invalid nonnegative count: " + label)
    return value


def validate(queue, diagnostics):
    if not isinstance(queue, dict) or not isinstance(diagnostics, dict):
        raise ValueError("queue and diagnostics must be objects")
    if queue.get("ex_final_allowed") is not False or queue.get("score_verified") is not False:
        raise ValueError("review queue must remain unverified")
    total = _count(queue.get("total_review_queue"), "total_review_queue")
    if total != _count(diagnostics.get("unmatched_total"), "unmatched_total"):
        raise ValueError("queue total differs from diagnostics")
    fixtures = queue.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError("fixtures must be a list")
    exported = _count(queue.get("exported"), "exported")
    if exported != len(fixtures) or exported > total:
        raise ValueError("incorrect exported fixture count")
    if type(queue.get("truncated")) is not bool or queue["truncated"] != (exported < total):
        raise ValueError("incorrect truncation marker")
    if type(queue.get("queue_version")) is not int or queue["queue_version"] != 2:
        raise ValueError("unsupported review queue version")
    by_league = diagnostics.get("by_league")
    if not isinstance(by_league, dict):
        raise ValueError("diagnostic league counts missing")
    league_counts = {}
    for league, row in by_league.items():
        if not isinstance(league, str) or not league or not isinstance(row, dict):
            raise ValueError("invalid league diagnostic")
        league_counts[league] = _count(row.get("count"), "league count")
    if sum(league_counts.values()) != total:
        raise ValueError("diagnostic league totals disagree")
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise ValueError("invalid queue fixture")
        if (fixture.get("league") not in league_counts
                or fixture.get("review_status") != "REQUIRES_INDEPENDENT_SOURCE_REVIEW"):
            raise ValueError("unexpected queue fixture")
    return {"total": total, "exported": exported, "by_league": league_counts,
            "score_verified": False, "ex_final_allowed": False}
