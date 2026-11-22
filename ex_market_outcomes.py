"""EX v4.3 market outcome labels from audited, completed fixture results.

Labels are realized outcomes (0/1), NOT model probabilities or EX FINAL picks.
The fixture perspective is the home/away perspective, never the selected team.
"""
import datetime as dt

MARKETS = ("MS1", "MS2", "KG_VAR", "2.5_UST")


def market_outcomes(fixtures, as_of):
    issues = []
    try:
        if not isinstance(as_of, str) or not as_of.endswith("Z"):
            raise ValueError("UTC cutoff required")
        cutoff = dt.datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if cutoff.utcoffset() != dt.timedelta(0):
            raise ValueError("timezone missing")
    except (TypeError, ValueError, OverflowError):
        return {"status": "BLOCKED", "issues": ["as_of:invalid"], "outcomes": [],
                "ex_final_allowed": False}
    if not isinstance(fixtures, list) or not fixtures:
        return {"status": "BLOCKED", "issues": ["fixtures:missing"], "outcomes": [],
                "ex_final_allowed": False}
    seen = set()
    labels = []
    for i, row in enumerate(fixtures):
        if not isinstance(row, dict):
            issues.append("fixture:%d:invalid" % i)
            continue
        fid = row.get("fixture_id")
        if not isinstance(fid, str) or not fid.strip() or fid in seen:
            issues.append("fixture:%d:duplicate_or_missing_id" % i)
        else:
            seen.add(fid)
        if row.get("verified") is not True or not isinstance(row.get("source"), str) or not row["source"].strip():
            issues.append("fixture:%d:unverified" % i)
        if row.get("status") != "finished":
            issues.append("fixture:%d:not_finished" % i)
        home, away = row.get("home_goals"), row.get("away_goals")
        if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in (home, away)):
            issues.append("fixture:%d:score_invalid" % i)
            continue
        try:
            stamp = row["kickoff_at"]
            if not isinstance(stamp, str) or not stamp.endswith("Z"):
                raise ValueError("UTC kickoff required")
            when = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if when.utcoffset() != dt.timedelta(0) or when >= cutoff:
                raise ValueError("future fixture")
        except (KeyError, ValueError, TypeError, OverflowError):
            issues.append("fixture:%d:date_invalid_or_future" % i)
            continue
        labels.append({"fixture_id": fid, "kickoff_at": stamp,
                       "MS1": int(home > away), "MS2": int(away > home),
                       "KG_VAR": int(home > 0 and away > 0),
                       "2.5_UST": int(home + away >= 3)})
    return {"status": "OUTCOMES_READY" if not issues else "BLOCKED",
            "issues": issues, "outcomes": labels if not issues else [],
            "markets": MARKETS, "ex_final_allowed": False}
