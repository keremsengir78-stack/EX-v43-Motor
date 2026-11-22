"""Compact audit manifest for deterministic independent source review batches."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

def manifest(report):
    if report.get("ex_final_allowed") is not False or report.get("aliases_approved") is not False or report.get("independently_verified_added") != 0:
        raise ValueError("unverified source batches must remain blocked")
    rows=[]
    records=[]
    for batch in report.get("batches",[]):
        fixtures=batch.get("fixtures")
        if not isinstance(fixtures,list) or len(fixtures)!=batch.get("count"):
            raise ValueError("invalid batch")
        league_counts=Counter()
        for fixture in fixtures:
            if fixture.get("independent_score_verified") is not False or fixture.get("review_status")!="PENDING_SOURCE_REVIEW":
                raise ValueError("unsafe source review state")
            row={k:fixture.get(k) for k in ("league","season","date","home","away","reason")}
            if any(not isinstance(v,str) or not v for v in row.values()):
                raise ValueError("incomplete fixture identity")
            rows.append(row)
            league_counts[row["league"]]+=1
        digest=hashlib.sha256(json.dumps(
            [{k:f.get(k) for k in ("league","season","date","home","away","reason")} for f in fixtures],
            ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        records.append({"batch_id":batch.get("batch_id"),"count":len(fixtures),
                        "by_league":dict(sorted(league_counts.items())),"sha256":digest,
                        "review_status":"PENDING_SOURCE_REVIEW"})
    if len(rows)!=report.get("total_unmatched") or len(records)!=report.get("batch_count"):
        raise ValueError("incomplete batch manifest")
    return {"total_unmatched":len(rows),"batch_count":len(records),"batches":records,
            "independently_verified_added":0,"ex_final_allowed":False}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--batches",required=True)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    result=manifest(json.loads(Path(args.batches).read_text(encoding="utf-8")))
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")

if __name__=="__main__":
    main()
