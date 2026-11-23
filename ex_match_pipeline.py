"""End-to-end verified-record evidence processing for one EX v4.3 market.

Accepts already collected fixture records and explicitly audited EX-G inputs.
This is not an online data fetcher and never promotes evidence to EX FINAL.
"""
from ex_window_builder import build_windows
from ex_evidence_pipeline import prepare_market_evidence
from ex_source_agreement import verify_fixture_sources


def process_match_evidence(market, records, venue, season, previous_season,
                           feature_scores, as_of, source_observations=None, require_evidence_locator=False):
    # Source agreement is mandatory for every historical fixture.
    if not isinstance(records, list) or not isinstance(source_observations, dict):
        return {"status": "BLOCKED", "issues": ["sources:missing"],
                "windows": None, "evidence": None, "calibrated_probability": None,
                "pup_allowed": False, "ex_final_allowed": False}
    source_issues = []
    for i, row in enumerate(records):
        fixture_id = row.get("fixture_id") if isinstance(row, dict) else None
        observations = source_observations.get(fixture_id) if isinstance(fixture_id, str) else None
        checked = verify_fixture_sources(observations, as_of,
                                         require_evidence_locator=require_evidence_locator)
        if checked["status"] != "CROSS_VERIFIED_INPUT":
            source_issues.extend("fixture:%d:%s" % (i, issue) for issue in checked["issues"])
            continue
        agreed = checked["agreed_fixture"]
        # Never silently trust a record that contradicts either source.
        if (not isinstance(row, dict) or
                any(row.get(key) != agreed[key] for key in
                    ("fixture_id", "kickoff_at", "home_goals", "away_goals"))):
            source_issues.append("fixture:%d:record_conflict" % i)
        if isinstance(row, dict):
            for team_field in ("home_team", "away_team"):
                if team_field in row and row[team_field] != agreed[team_field]:
                    source_issues.append("fixture:%d:team_identity_conflict" % i)
            match_venue = row.get("venue")
            if match_venue not in ("home", "away"):
                source_issues.append("fixture:%d:venue_invalid" % i)
            else:
                expected_for = agreed["home_goals"] if match_venue == "home" else agreed["away_goals"]
                expected_against = agreed["away_goals"] if match_venue == "home" else agreed["home_goals"]
                if (row.get("goals_for") != expected_for or
                        row.get("goals_against") != expected_against):
                    source_issues.append("fixture:%d:venue_score_conflict" % i)
    if source_issues:
        return {"status": "BLOCKED", "issues": source_issues,
                "windows": None, "evidence": None, "calibrated_probability": None,
                "pup_allowed": False, "ex_final_allowed": False}
    built = build_windows(records, venue, season, previous_season, as_of)
    if built["status"] != "WINDOWS_READY":
        return {"status": "BLOCKED", "issues": ["window:" + x for x in built["issues"]],
                "windows": built, "evidence": None, "calibrated_probability": None,
                "pup_allowed": False, "ex_final_allowed": False}
    evidence = prepare_market_evidence(market, built["windows"], feature_scores, as_of)
    return {"status": "EVIDENCE_READY_UNCALIBRATED"
            if evidence["status"] == "EVIDENCE_READY_UNCALIBRATED" else "BLOCKED",
            "issues": evidence["issues"], "windows": built, "evidence": evidence,
            "calibrated_probability": None, "pup_allowed": False,
            "ex_final_allowed": False}
