"""Cross-check all exported score review batches against the original report.

This is a structural integrity audit, not independent score verification.
"""


def audit_review_exports(source, batches):
    issues = []
    if not isinstance(source, dict) or not isinstance(batches, list):
        return {"status": "BLOCKED", "issues": ["inputs:invalid"],
                "ex_final_allowed": False, "independent_score_verified": False}
    rows = source.get("verified")
    if (not isinstance(rows, list) or type(source.get("confirmed")) is not int
            or type(source.get("total")) is not int
            or type(source.get("remaining")) is not int
            or source["confirmed"] != len(rows)
            or source["total"] != source["confirmed"] + source["remaining"]):
        return {"status": "BLOCKED", "issues": ["source:invalid_counts"],
                "ex_final_allowed": False, "independent_score_verified": False}
    seen = set()
    leagues = {}
    providers = {}
    for batch_index, batch in enumerate(batches):
        if not isinstance(batch, dict) or not isinstance(batch.get("fixtures"), list):
            issues.append("batch:%d:invalid" % batch_index)
            continue
        fixtures = batch["fixtures"]
        if (batch.get("ex_final_allowed") is not False
                or batch.get("independent_score_verified") is not False
                or type(batch.get("offset")) is not int
                or type(batch.get("exported")) is not int
                or batch["exported"] != len(fixtures)
                or batch.get("source_total") != source["total"]):
            issues.append("batch:%d:metadata_mismatch" % batch_index)
        for row in fixtures:
            if not isinstance(row, dict) or type(row.get("index")) is not int:
                issues.append("batch:%d:invalid_fixture" % batch_index)
                continue
            index = row["index"]
            if index < 0 or index >= len(rows) or index in seen:
                issues.append("fixture:%d:duplicate_or_out_of_range" % index)
                continue
            seen.add(index)
            original = rows[index]
            fixture = original.get("fixture", {})
            expected = {
                "league": fixture.get("league"), "season": fixture.get("season"),
                "date": fixture.get("date"), "home": fixture.get("home"),
                "away": fixture.get("away"), "matched_score": original.get("score"),
                "secondary_provider": original.get("secondary_provider"),
                "secondary_url": original.get("secondary_url"),
                "secondary_sha256": original.get("secondary_sha256"),
            }
            if (any(row.get(k) != v for k, v in expected.items())
                    or row.get("independent_score_verified") is not False
                    or row.get("review_status") != "REQUIRES_INDEPENDENT_SCORE_EVIDENCE"):
                issues.append("fixture:%d:source_mismatch" % index)
            league = row.get("league")
            provider = row.get("secondary_url")
            if isinstance(league, str):
                leagues[league] = leagues.get(league, 0) + 1
            if isinstance(provider, str):
                providers[provider] = providers.get(provider, 0) + 1
    if len(seen) != len(rows):
        issues.append("coverage:missing_records")
    if len(batches) != (len(rows) + 99) // 100:
        issues.append("batches:incorrect_count")
    for i, batch in enumerate(batches):
        if not isinstance(batch, dict):
            continue
        expected_offset = i * 100
        fixtures = batch.get("fixtures")
        if (batch.get("offset") != expected_offset
                or not isinstance(fixtures, list)
                or [r.get("index") if isinstance(r, dict) else None for r in fixtures]
                   != list(range(expected_offset, min(expected_offset + 100, len(rows))))
                or batch.get("truncated") is not (expected_offset + len(fixtures) < len(rows))):
            issues.append("batch:%d:pagination_mismatch" % i)
    return {
        "status": "EXPORT_INTEGRITY_PASSED_NOT_SOURCE_VERIFIED" if not issues else "BLOCKED",
        "issues": issues, "source_total": source["total"],
        "exported_unique": len(seen), "league_counts": leagues,
        "source_url_counts": providers, "independent_score_verified": False,
        "ex_final_allowed": False,
    }
