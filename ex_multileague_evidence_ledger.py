"""Create a review-ready, non-approved independent source evidence ledger."""
import argparse
import json
from pathlib import Path

def create(batches, batch_id=1):
    if batches.get("ex_final_allowed") is not False or batches.get("independently_verified_added") != 0:
        raise ValueError("unsafe source batches")
    selected=[b for b in batches.get("batches",[]) if b.get("batch_id")==batch_id]
    if len(selected)!=1:
        raise ValueError("batch not found or ambiguous")
    records=[]
    for fixture in selected[0].get("fixtures",[]):
        if fixture.get("review_status")!="PENDING_SOURCE_REVIEW" or fixture.get("independent_score_verified") is not False:
            raise ValueError("fixture prematurely approved")
        records.append({
            "league":fixture["league"],"season":fixture["season"],
            "date":fixture["date"],"home":fixture["home"],"away":fixture["away"],
            "source_presence_reason":fixture["reason"],
            "independent_source_url":None,"independent_source_provider":None,
            "independent_source_retrieved_at":None,
            "independent_home":None,"independent_away":None,
            "independent_home_goals":None,"independent_away_goals":None,
            "date_confirmed":False,"teams_confirmed":False,"score_confirmed":False,
            "review_status":"AWAITING_INDEPENDENT_SOURCE",
        })
    if len(records)!=selected[0].get("count"):
        raise ValueError("incomplete batch")
    return {"batch_id":batch_id,"total_records":len(records),
            "records":records,"independently_verified_added":0,
            "ex_final_allowed":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--batches",required=True)
    p.add_argument("--batch-id",type=int,default=1)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=create(json.loads(Path(a.batches).read_text(encoding="utf-8")),a.batch_id)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")

if __name__=="__main__":
    main()
