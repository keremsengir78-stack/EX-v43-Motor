"""Auditable fixture and odds gates. No inferred fixture, price, or kickoff."""
import datetime as dt
import math

def check_fixture(fixture, as_of):
    issues=[]
    if not isinstance(fixture,dict):
        return {"status":"BLOCKED","issues":["fixture:missing"],"ex_final_allowed":False}
    for field in ("date","league","home","away","fixture_source","fixture_checked_at","kickoff_at"):
        if not isinstance(fixture.get(field),str) or not fixture[field].strip():
            issues.append(field+":missing")
    try:
        kickoff=dt.date.fromisoformat(fixture["date"])
        if kickoff<dt.date.fromisoformat(as_of):
            issues.append("fixture:historical")
    except (KeyError,ValueError,TypeError):
        issues.append("fixture:invalid_date")
    try:
        kickoff_at=dt.datetime.fromisoformat(fixture["kickoff_at"].replace("Z","+00:00"))
        if kickoff_at.tzinfo is None:
            issues.append("kickoff_at:timezone_missing")
        elif kickoff_at.date()!=dt.date.fromisoformat(fixture["date"]):
            issues.append("kickoff_at:date_mismatch")
    except (KeyError,ValueError,TypeError,AttributeError):
        issues.append("kickoff_at:invalid")
    # A fixture lock is valid only when its source was checked before kickoff.
    try:
        checked=dt.datetime.fromisoformat(fixture["fixture_checked_at"].replace("Z","+00:00"))
        kickoff_time=dt.datetime.fromisoformat(fixture["kickoff_at"].replace("Z","+00:00"))
        if checked.tzinfo is None:
            issues.append("fixture_checked_at:timezone_missing")
        elif kickoff_time.tzinfo is not None and checked>=kickoff_time:
            issues.append("fixture:checked_after_kickoff")
    except (KeyError,ValueError,TypeError,AttributeError):
        issues.append("fixture_checked_at:invalid")
    if fixture.get("home")==fixture.get("away"):
        issues.append("fixture:identical_teams")
    return {"status":"VERIFIED_INPUT" if not issues else "BLOCKED",
            "issues":issues,"ex_final_allowed":False}

def check_odds(snapshot, as_of):
    issues=[]
    if not isinstance(snapshot,dict):
        return {"status":"BLOCKED","issues":["odds:missing"],"decision":"NO_FINAL"}
    try:
        raw=snapshot["decimal_odds"]
        if isinstance(raw,bool):
            raise ValueError("boolean odds are invalid")
        odd=float(raw)
        if not math.isfinite(odd) or odd<=1:
            issues.append("odds:invalid")
    except (ValueError,TypeError,KeyError):
        odd=None
        issues.append("odds:missing")
    for field in ("market","bookmaker","observed_at","source"):
        if not isinstance(snapshot.get(field),str) or not snapshot[field].strip():
            issues.append(field+":missing")
    # Never allow an unmodelled market to masquerade as an audited EX selection.
    if isinstance(snapshot.get("market"),str) and snapshot["market"].strip() and snapshot["market"] not in ("2.5_UST","KG_VAR","MS1","MS2"):
        issues.append("market:unsupported")
    try:
        observed=dt.datetime.fromisoformat(snapshot["observed_at"].replace("Z","+00:00"))
        cutoff=dt.datetime.fromisoformat(as_of.replace("Z","+00:00"))
        if observed.tzinfo is None or cutoff.tzinfo is None:
            issues.append("odds:timezone_missing")
        elif observed>=cutoff:
            issues.append("odds:not_before_kickoff")
    except (KeyError,ValueError,TypeError,AttributeError):
        issues.append("odds:invalid_timestamp")
    return {"status":"VERIFIED_INPUT" if not issues else "BLOCKED",
            "issues":issues,
            "decision":"PASS_ODDS_1_19_OR_LOWER" if not issues and odd<=1.19 else "NO_FINAL",
            "ex_final_allowed":False}
