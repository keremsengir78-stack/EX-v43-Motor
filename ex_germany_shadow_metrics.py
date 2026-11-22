"""Validate isolated Germany shadow results without approving source evidence."""


def validate_shadow_metrics(baseline, shadow, offline):
    if any(x.get("ex_final_allowed") is not False for x in (shadow, offline)):
        raise ValueError("shadow evidence must keep EX FINAL locked")
    if shadow.get("aliases_approved") is not False or offline.get("aliases_approved") is not False:
        raise ValueError("candidate aliases cannot be approved")
    before = baseline.get("germany_unmatched")
    after = shadow.get("shadow_germany_unmatched")
    name_only = offline.get("unique_name_only_candidates")
    if any(type(n) is not int or n < 0 for n in (before, after, name_only)):
        raise ValueError("missing or invalid comparison counts")
    if offline.get("germany_unmatched_baseline") != before:
        raise ValueError("offline baseline disagrees with source")
    if after > before:
        raise ValueError("shadow unmatched count increased unexpectedly")
    if offline.get("verified_score_matches_added") != 0:
        raise ValueError("name-only matches cannot be score verified")
    if shadow.get("shadow_source_errors"):
        raise ValueError("shadow secondary source errors")
    if type(shadow.get("shadow_score_conflicts")) is not int:
        raise ValueError("missing score conflict count")
    return {"baseline_unmatched": before, "shadow_unmatched": after,
            "shadow_reduction": before - after,
            "name_only_candidates": name_only,
            "shadow_score_conflicts": shadow["shadow_score_conflicts"],
            "independently_verified_added": 0,
            "comparison_only": True, "aliases_approved": False,
            "ex_final_allowed": False}
