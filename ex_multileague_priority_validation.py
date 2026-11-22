"""Fail-closed cross-check for a non-German independent source review plan."""


def validate(plan, diagnostics, shadow):
    for obj in (plan, diagnostics, shadow):
        if obj.get("ex_final_allowed") is not False:
            raise ValueError("EX FINAL lock missing")
    if plan.get("aliases_approved") is not False or plan.get("independently_verified_added") != 0:
        raise ValueError("priority plan cannot approve evidence")
    if diagnostics.get("score_verified") is not False:
        raise ValueError("diagnostics must not claim score verification")
    expected=shadow.get("shadow_unmatched")
    if type(expected) is not int or expected < 0:
        raise ValueError("invalid shadow total")
    if plan.get("total_unmatched") != expected or diagnostics.get("unmatched_total") != expected:
        raise ValueError("cross-report mismatch")
    observed={}
    for bucket in plan.get("priority_buckets",[]):
        league,reason,count=bucket.get("league"),bucket.get("reason"),bucket.get("count")
        if league not in ("en.1","es.1","it.1") or type(count) is not int or count<1:
            raise ValueError("invalid bucket")
        key=(league,reason)
        if key in observed or bucket.get("auto_approved") is not False:
            raise ValueError("duplicate or unsafe bucket")
        if bucket.get("priority_score") != count*{"SECONDARY_SAME_DAY_SHARED_TEAM":3,"SECONDARY_DATE_PRESENT_NO_TEAM_MATCH":2,"SECONDARY_DATE_EMPTY":1}.get(reason,-999):
            raise ValueError("priority score mismatch")
        actual=diagnostics.get("by_league",{}).get(league,{}).get("source_presence",{}).get(reason)
        if actual != count:
            raise ValueError("source presence count mismatch")
        observed[key]=count
    expected_buckets={(league,reason):count
        for league,data in diagnostics.get("by_league",{}).items()
        if league in ("en.1","es.1","it.1")
        for reason,count in data.get("source_presence",{}).items() if count>0}
    if observed != expected_buckets or sum(observed.values())!=expected:
        raise ValueError("incomplete priority buckets")
    return {"total_unmatched":expected,"validated_buckets":len(observed),
            "independently_verified_added":0,"ex_final_allowed":False}
