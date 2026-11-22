"""Identify one-to-one same-day source candidates, without approving match scores."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

def select(report, threshold=0.90, margin=0.08):
    if report.get("ex_final_allowed") is not False or report.get("independently_verified_added")!=0:
        raise ValueError("unsafe candidate report")
    records=report.get("records")
    if not isinstance(records,list) or len(records)!=report.get("total_fixtures"):
        raise ValueError("candidate report truncated")
    claims=defaultdict(list)
    possible=[]
    for i,r in enumerate(records):
        options=r.get("candidates")
        if not isinstance(options,list) or r.get("independent_score_verified") is not False:
            raise ValueError("unsafe candidate record")
        if not options or r.get("source_error"):continue
        first=options[0]
        similarity=first.get("name_similarity",0)
        runner_up=options[1].get("name_similarity",0) if len(options)>1 else 0
        if (similarity>=threshold and first.get("home_similarity",0)>=0.85
            and first.get("away_similarity",0)>=0.85 and similarity-runner_up>=margin):
            f=r["fixture"]
            key=(f["league"],f["season"],f["date"],first["home"],first["away"])
            claims[key].append(i)
            possible.append((i,key,similarity))
    unique=[]
    for i,key,similarity in possible:
        if len(claims[key])!=1:continue
        r=records[i]
        unique.append({"fixture":r["fixture"],"candidate":r["candidates"][0],
                       "source_provider":r.get("source_provider"),
                       "source_url":r.get("source_url"),"source_sha256":r.get("source_sha256"),
                       "name_similarity":similarity,"review_status":"HIGH_CONFIDENCE_NAME_CANDIDATE",
                       "independent_score_verified":False})
    return {"total_fixtures":len(records),"unique_name_candidates":len(unique),
            "remaining_for_manual_review":len(records)-len(unique),
            "records":unique,"independently_verified_added":0,"ex_final_allowed":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidates",required=True);p.add_argument("--out",required=True)
    a=p.parse_args()
    result=select(json.loads(Path(a.candidates).read_text(encoding="utf-8")))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":main()
