"""Fail-closed validation for unverified independent-source evidence ledger entries."""


def validate(ledger, batches):
    if ledger.get("ex_final_allowed") is not False or ledger.get("independently_verified_added")!=0:
        raise ValueError("evidence ledger cannot authorize EX FINAL")
    bid=ledger.get("batch_id")
    candidates=[b for b in batches.get("batches",[]) if b.get("batch_id")==bid]
    if len(candidates)!=1:
        raise ValueError("unknown batch")
    expected=candidates[0].get("fixtures")
    records=ledger.get("records")
    if not isinstance(expected,list) or not isinstance(records,list) or len(records)!=len(expected) or ledger.get("total_records")!=len(expected):
        raise ValueError("ledger coverage mismatch")
    for row,fixture in zip(records,expected):
        for key in ("league","season","date","home","away"):
            if row.get(key)!=fixture.get(key):
                raise ValueError("fixture identity mismatch")
        if row.get("source_presence_reason")!=fixture.get("reason"):
            raise ValueError("source diagnosis mismatch")
        for key in ("independent_source_url","independent_source_provider",
                    "independent_source_retrieved_at","independent_home","independent_away",
                    "independent_home_goals","independent_away_goals"):
            if row.get(key) is not None:
                raise ValueError("unreviewed evidence must be empty")
        if any(row.get(key) is not False for key in ("date_confirmed","teams_confirmed","score_confirmed")):
            raise ValueError("unreviewed fixture cannot be confirmed")
        if row.get("review_status")!="AWAITING_INDEPENDENT_SOURCE":
            raise ValueError("invalid pending evidence state")
    return {"batch_id":bid,"records_checked":len(records),
            "independently_verified_added":0,"ex_final_allowed":False}
