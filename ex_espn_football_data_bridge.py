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


def fetch_and_compare_historical_day(league, season, day, as_of, offline_secondary=None, alias=None):
    """Fetch a dated ESPN scoreboard and secondary season CSV, then compare.

    Both provider observations remain provisional even when scores match.
    The secondary CSV can be supplied offline for reproducible evaluation.
    """
    import datetime as dt
    from ex_espn_provider import ESPN_LEAGUES, fetch_espn_scoreboard
    from ex_cross_verify import DIVISIONS, secondary_rows, validate_third_results
    base = {"status": "BLOCKED", "comparison": None, "issues": [],
            "provenance": {}, "independent_sources_confirmed": False,
            "calibration_certified": False, "ex_final_allowed": False}
    try:
        if league not in ESPN_LEAGUES or league not in DIVISIONS:
            raise ValueError("league:unsupported")
        requested = dt.date.fromisoformat(day)
        cutoff = dt.date.fromisoformat(as_of)
        start_year, end_year = (int(x) for x in season.split("-"))
        if (end_year != start_year + 1
                or not dt.date(start_year, 7, 1) <= requested <= dt.date(end_year, 6, 30)):
            raise ValueError("season:invalid_or_mismatched")
        if requested >= cutoff:
            raise ValueError("day:at_or_after_cutoff")
    except (AttributeError, TypeError, ValueError) as exc:
        base["issues"] = [str(exc) if str(exc).startswith(("league:", "season:", "day:")) else "input:invalid"]
        return base
    try:
        espn, espn_meta = fetch_espn_scoreboard(league, day, as_of)
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        base["issues"] = ["espn:fetch_or_parse_failed"]
        return base
    secondary, secondary_meta = secondary_rows(season, league, offline=offline_secondary)
    base["provenance"] = {"espn": espn_meta, "football_data": secondary_meta}
    if "error" in secondary_meta:
        base["issues"] = ["football_data:fetch_or_parse_failed"]
        return base
    try:
        filtered = validate_third_results(
            [row for row in secondary if row["date"] == day], as_of)
    except (KeyError, TypeError, ValueError):
        base["issues"] = ["football_data:missing_or_invalid_day"]
        return base
    result = compare_espn_football_data(espn, filtered, as_of, alias=alias)
    base.update(result)
    base["provenance"] = {"espn": espn_meta, "football_data": secondary_meta}
    return base
