"""Cross-validate every source-review batch against the audited post-shadow summary."""


def validate(batches, summary):
    if batches.get("ex_final_allowed") is not False or batches.get("aliases_approved") is not False:
        raise ValueError("review batches must remain quarantined")
    if batches.get("independently_verified_added") != 0 or summary.get("ex_final_allowed") is not False:
        raise ValueError("source evidence not approved")
    expected=summary.get("unmatched_total")
    if type(expected) is not int or expected<0 or batches.get("total_unmatched")!=expected:
        raise ValueError("unmatched total mismatch")
    size=batches.get("batch_size")
    if type(size) is not int or size<1:
        raise ValueError("invalid batch size")
    actual_batches=batches.get("batches")
    if not isinstance(actual_batches,list) or batches.get("batch_count")!=len(actual_batches):
        raise ValueError("batch count mismatch")
    expected_keys=set()
    for group in summary.get("groups",[]):
        if group.get("league") not in ("en.1","es.1","it.1"):
            if group.get("unmatched_count")!=0:
                raise ValueError("unexpected unresolved league")
            continue
        fixtures=group.get("unmatched_details")
        if not isinstance(fixtures,list) or len(fixtures)!=group.get("unmatched_count"):
            raise ValueError("truncated source evidence")
        for r in fixtures:
            key=(group["league"],group["season"],r.get("date"),r.get("home"),r.get("away"))
            if key in expected_keys:
                raise ValueError("duplicate source fixture")
            expected_keys.add(key)
    observed=set()
    cursor=0
    for i,batch in enumerate(actual_batches):
        fixtures=batch.get("fixtures")
        if batch.get("batch_id")!=i+1 or batch.get("start_index")!=cursor or not isinstance(fixtures,list):
            raise ValueError("out of order batch")
        if batch.get("count")!=len(fixtures) or not (0<len(fixtures)<=size):
            raise ValueError("invalid batch size")
        if i<len(actual_batches)-1 and len(fixtures)!=size:
            raise ValueError("incomplete nonfinal batch")
        for r in fixtures:
            key=(r.get("league"),r.get("season"),r.get("date"),r.get("home"),r.get("away"))
            if key in observed or r.get("independent_score_verified") is not False or r.get("review_status")!="PENDING_SOURCE_REVIEW":
                raise ValueError("duplicate or unsafe review fixture")
            observed.add(key)
        cursor+=len(fixtures)
    if observed!=expected_keys or cursor!=expected:
        raise ValueError("batch coverage incomplete")
    return {"total_unmatched":expected,"batch_count":len(actual_batches),
            "fixtures_checked":cursor,"independently_verified_added":0,
            "ex_final_allowed":False}
