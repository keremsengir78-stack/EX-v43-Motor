"""Fail-closed arithmetic and safety checks for non-German shadow comparison."""


def validate(comparison, diagnostics):
    if any(comparison.get(key) is not False for key in ("ex_final_allowed","aliases_approved")):
        raise ValueError("shadow aliases must remain unapproved")
    if comparison.get("comparison_only") is not True or comparison.get("independently_verified_added") != 0:
        raise ValueError("shadow cannot count as independent score evidence")
    if diagnostics.get("ex_final_allowed") is not False or diagnostics.get("score_verified") is not False:
        raise ValueError("diagnostic evidence must remain quarantined")
    original=comparison.get("baseline_unmatched")
    remaining=comparison.get("shadow_unmatched")
    if type(original) is not int or type(remaining) is not int or not (0<=remaining<=original):
        raise ValueError("invalid baseline or remaining mismatch totals")
    by_league=comparison.get("shadow_unmatched_by_league")
    if not isinstance(by_league,dict) or set(by_league)!={"en.1","es.1","it.1","fr.1"}:
        raise ValueError("missing four-league shadow coverage")
    if any(type(v) is not int or v<0 for v in by_league.values()) or sum(by_league.values())!=remaining:
        raise ValueError("shadow league totals disagree")
    diagnostic_leagues=diagnostics.get("by_league",{})
    if {league:diagnostic_leagues.get(league,{}).get("count",0) for league in by_league}!=by_league:
        raise ValueError("diagnostic and shadow league totals disagree")
    if diagnostics.get("unmatched_total")!=remaining:
        raise ValueError("diagnostic total differs")
    if comparison.get("score_conflicts")!=0 or comparison.get("source_errors")!=[]:
        raise ValueError("shadow contains conflicts or source errors")
    return {"baseline_unmatched":original,"shadow_unmatched":remaining,
            "name_only_reduction":original-remaining,"by_league":by_league,
            "independently_verified_added":0,"ex_final_allowed":False}
