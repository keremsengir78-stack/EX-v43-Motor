"""Validate quarantined expanded shadow comparison, without authorizing EX FINAL."""


def validate(base, first, expanded, candidate_reports):
    original=base.get("germany_unmatched")
    first_unmatched=first.get("shadow_germany_unmatched")
    expanded_unmatched=expanded.get("expanded_shadow_unmatched")
    counts=[original,first_unmatched,expanded_unmatched]
    if any(type(x) is not int or x<0 for x in counts):
        raise ValueError("invalid shadow counts")
    if not (original>=first_unmatched>=expanded_unmatched):
        raise ValueError("shadow mismatch count is not monotonic")
    if any(x.get("ex_final_allowed") is not False for x in [first,expanded,*candidate_reports]):
        raise ValueError("EX FINAL lock missing")
    if expanded.get("aliases_approved") is not False or expanded.get("comparison_only") is not True:
        raise ValueError("expanded run must remain quarantined")
    if expanded.get("independently_verified_added") != 0:
        raise ValueError("shadow result cannot claim independently verified scores")
    if expanded.get("expanded_shadow_source_errors"):
        raise ValueError("expanded shadow source errors")
    if type(expanded.get("expanded_shadow_score_conflicts")) is not int:
        raise ValueError("missing expanded score conflict count")
    if expanded["expanded_shadow_score_conflicts"] != 0:
        raise ValueError("expanded shadow score conflict")
    pairs=[]
    primary_to_secondary={}
    secondary_to_primary={}
    for report in candidate_reports:
        for row in report.get("candidates",[]):
            if row.get("mapping_conflict") is not False or row.get("auto_approved") is not False:
                raise ValueError("conflicting or approved candidate")
            p,s=row.get("primary_name"),row.get("secondary_name")
            if not isinstance(p,str) or not p.strip() or not isinstance(s,str) or not s.strip():
                raise ValueError("invalid candidate name")
            if (p in primary_to_secondary and primary_to_secondary[p]!=s) or (s in secondary_to_primary and secondary_to_primary[s]!=p):
                raise ValueError("cross-report mapping conflict")
            primary_to_secondary[p]=s
            secondary_to_primary[s]=p
            pairs.append((p,s))
    if len(pairs)!=expanded.get("candidate_count") or len(pairs)!=len(set(pairs)):
        raise ValueError("candidate count or duplicate mismatch")
    return {"baseline_unmatched":original,
            "first_shadow_unmatched":first_unmatched,
            "expanded_shadow_unmatched":expanded_unmatched,
            "shadow_name_reduction":original-expanded_unmatched,
            "new_shadow_name_reduction":first_unmatched-expanded_unmatched,
            "candidate_count":len(pairs),
            "score_conflicts":0,"independently_verified_added":0,
            "aliases_approved":False,"comparison_only":True,
            "ex_final_allowed":False}
