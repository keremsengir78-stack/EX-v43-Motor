"""Partition post-shadow unresolved fixtures into deterministic, auditable source-review batches."""
import argparse
import json
from pathlib import Path

PRIORITY={"SECONDARY_SAME_DAY_SHARED_TEAM":0,
          "SECONDARY_DATE_PRESENT_NO_TEAM_MATCH":1,
          "SECONDARY_DATE_EMPTY":2}

def build(summary, batch_size=50):
    if summary.get("ex_final_allowed") is not False or type(batch_size) is not int or batch_size<1:
        raise ValueError("invalid safety lock or batch size")
    rows=[]
    seen=set()
    for group in summary.get("groups",[]):
        league=group.get("league")
        if league not in ("en.1","es.1","it.1"):
            if group.get("unmatched_count")!=0:
                raise ValueError("unexpected unresolved league")
            continue
        details=group.get("unmatched_details")
        if not isinstance(details,list) or len(details)!=group.get("unmatched_count"):
            raise ValueError("truncated review group")
        for r in details:
            reason=r.get("source_presence_status")
            if reason not in PRIORITY:
                raise ValueError("unknown source status")
            key=(league,group.get("season"),r.get("date"),r.get("home"),r.get("away"))
            if key in seen:
                raise ValueError("duplicate fixture")
            seen.add(key)
            rows.append({"league":league,"season":group.get("season"),
                         "date":r.get("date"),"home":r.get("home"),
                         "away":r.get("away"),"reason":reason,
                         "independent_score_verified":False,
                         "review_status":"PENDING_SOURCE_REVIEW"})
    if len(rows)!=summary.get("unmatched_total"):
        raise ValueError("unmatched total mismatch")
    rows.sort(key=lambda r:(PRIORITY[r["reason"]],r["league"],str(r["date"]),
                            str(r["home"]),str(r["away"])))
    batches=[{"batch_id":i//batch_size+1,"start_index":i,
              "count":len(rows[i:i+batch_size]),"fixtures":rows[i:i+batch_size]}
             for i in range(0,len(rows),batch_size)]
    return {"total_unmatched":len(rows),"batch_size":batch_size,
            "batch_count":len(batches),"batches":batches,
            "independently_verified_added":0,"aliases_approved":False,
            "ex_final_allowed":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--summary",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--batch-size",type=int,default=50)
    a=p.parse_args()
    result=build(json.loads(Path(a.summary).read_text(encoding="utf-8")),a.batch_size)
    target=Path(a.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
    print(json.dumps({"unmatched":result["total_unmatched"],"batches":result["batch_count"]}))

if __name__=="__main__":
    main()
