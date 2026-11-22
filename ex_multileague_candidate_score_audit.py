"""Audit one-to-one name candidates against primary scores; never auto-approve identity."""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from ex_cross_verify import norm
from ex_engine import load

def audit(report, primary):
    if report.get("ex_final_allowed") is not False or report.get("independently_verified_added") != 0:
        raise ValueError("unsafe candidate report")
    records=report.get("records", [])
    if len(records)!=report.get("unique_name_candidates"):
        raise ValueError("truncated candidate report")
    index=defaultdict(list)
    for r in primary:
        index[(r["season"],str(r["date"]),r["league"],norm(r["home"]),norm(r["away"]))].append(r)
    seen=set()
    results=[]
    counts=Counter()
    for entry in records:
        f=entry["fixture"]; c=entry["candidate"]
        key=(f["season"],f["date"],f["league"],norm(f["home"]),norm(f["away"]))
        original=index.get(key,[])
        if key in seen:
            status="DUPLICATE_FIXTURE"
        elif len(original)!=1:
            status="PRIMARY_MISSING_OR_AMBIGUOUS"
        elif (original[0]["hg"],original[0]["ag"])!=(c["home_goals"],c["away_goals"]):
            status="SCORE_CONFLICT"
        else:
            status="SCORE_AGREES_IDENTITY_UNREVIEWED"
        seen.add(key)
        counts[status]+=1
        results.append({"fixture":f,"secondary_team_names":[c["home"],c["away"]],
                        "source_score":[c["home_goals"],c["away_goals"]],
                        "primary_score":[original[0]["hg"],original[0]["ag"]] if len(original)==1 else None,
                        "status":status,"independent_score_verified":False})
    return {"total_candidates":len(results),"counts":dict(counts),"records":results,
            "independently_verified_added":0,"ex_final_allowed":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidates",required=True)
    p.add_argument("--primary",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=audit(json.loads(Path(a.candidates).read_text(encoding="utf-8")),load(a.primary))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"total_candidates":result["total_candidates"],"counts":result["counts"]}))

if __name__=="__main__":
    main()
