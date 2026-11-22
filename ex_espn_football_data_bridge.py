"""Compare ESPN scoreboard observations with football-data.co.uk score rows.

This is a provisional provider-to-provider comparison. Matching scores do not
establish independent provenance, calibration or permission for EX FINAL.
"""
from ex_cross_verify import verify


def compare_espn_football_data(espn_rows, football_data_rows, as_of, alias=None):
    if not isinstance(espn_rows, list) or not isinstance(football_data_rows, list):
        return {"status": "BLOCKED", "issues": ["providers:invalid"],
                "comparison": None, "ex_final_allowed": False}
    if not espn_rows or not football_data_rows:
        return {"status": "BLOCKED", "issues": ["providers:empty"],
                "comparison": None, "ex_final_allowed": False}
    try:
        import datetime as dt
        cutoff = dt.date.fromisoformat(as_of)
        for rows in (espn_rows, football_data_rows):
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError("invalid row")
                day = dt.date.fromisoformat(row["date"])
                if day >= cutoff:
                    raise ValueError("future row")
                for field in ("league", "home", "away"):
                    if not isinstance(row[field], str) or not row[field].strip():
                        raise ValueError("invalid team or league")
                for field in ("home_goals", "away_goals"):
                    score = row[field]
                    if type(score) is not int or not 0 <= score <= 30:
                        raise ValueError("invalid score")
        result = verify(espn_rows, football_data_rows, as_of, alias)
    except (KeyError, TypeError, ValueError, AttributeError):
        return {"status": "BLOCKED", "issues": ["providers:malformed_or_future"],
                "comparison": None, "ex_final_allowed": False}
    if result["conflicts"]:
        status = "SCORE_CONFLICT"
    elif result["unmatched"] or result["ambiguous"]:
        status = "PARTIAL_PROVISIONAL_MATCH"
    else:
        status = "PROVISIONAL_MATCH_UNAUDITED"
    return {"status": status, "issues": [],
            "comparison": result, "independent_sources_confirmed": False,
            "calibration_certified": False, "ex_final_allowed": False}
