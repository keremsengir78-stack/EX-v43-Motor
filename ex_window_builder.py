"""Build EX v4.3 venue windows from audited, chronological fixture records.

Input records already represent one team's perspective. A fixture can be reused
across the overlapping windows, but duplicate fixture IDs in the input are
rejected. Source verification is not inferred by this module.
"""
import datetime as dt

def build_windows(records, venue, season, previous_season, as_of):
    issues = []
    if venue not in ("home", "away"):
        issues.append("venue:invalid")
    if not isinstance(season, str) or not season.strip() or not isinstance(previous_season, str) or not previous_season.strip() or season == previous_season:
        issues.append("season:invalid")
    try:
        if not isinstance(as_of, str) or not as_of.endswith("Z"):
            raise ValueError("UTC timestamp required")
        cutoff = dt.datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if cutoff.tzinfo is None:
            raise ValueError("timezone required")
    except (ValueError, TypeError, OverflowError):
        cutoff = None
        issues.append("as_of:invalid")
    if not isinstance(records, list):
        records = []
        issues.append("records:invalid")
    unique = set()
    clean = []
    for i, row in enumerate(records):
        if not isinstance(row, dict):
            issues.append("record:%d:invalid" % i)
            continue
        fixture_id = row.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id.strip() or fixture_id in unique:
            issues.append("record:%d:duplicate_or_missing_fixture" % i)
        else:
            unique.add(fixture_id)
        if row.get("venue") not in ("home", "away") or not isinstance(row.get("season"), str) or not row["season"].strip():
            issues.append("record:%d:venue_or_season_invalid" % i)
        if row.get("verified") is not True or not isinstance(row.get("source"), str) or not row["source"].strip():
            issues.append("record:%d:unverified" % i)
        try:
            stamp = row["kickoff_at"]
            if not isinstance(stamp, str) or not stamp.endswith("Z"):
                raise ValueError("UTC required")
            when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if when.tzinfo is None or (cutoff is not None and when >= cutoff):
                raise ValueError("future evidence")
        except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
            issues.append("record:%d:date_invalid_or_future" % i)
            continue
        clean.append((when, row))
    if issues:
        return {"status": "BLOCKED", "issues": issues, "windows": {},
                "ex_final_allowed": False}
    clean.sort(key=lambda pair: pair[0], reverse=True)
    current = [row for _, row in clean if row["season"] == season]
    relevant = [row for row in current if row["venue"] == venue]
    previous = [row for _, row in clean if row["season"] == previous_season and row["venue"] == venue]
    venue_history = sorted(relevant + previous, key=lambda row: row["kickoff_at"], reverse=True)
    windows = {"venue_last5": venue_history[:5], "venue_last10": venue_history[:10],
               "current_season": current, "previous_venue": previous}
    for key, value in windows.items():
        if len(value) < (10 if key == "venue_last10" else 5 if key == "venue_last5" else 1):
            issues.append(key + ":sample_incomplete")
    return {"status": "WINDOWS_READY" if not issues else "BLOCKED",
            "issues": issues, "windows": windows if not issues else {},
            "ex_final_allowed": False}
