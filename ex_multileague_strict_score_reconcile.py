"""Strictly reconcile unresolved fixtures against primary and secondary scored rows.

No fuzzy aliases, no inferred scores. A match is accepted only when the
date, league, both normalized team names and both goals agree one-to-one.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from ex_engine import load
from ex_cross_verify import norm, secondary_rows

def reconcile(batches, primary, offline=None):
    if batches.get("ex_final_allowed") is not False:
        raise ValueError("unsafe review batches")
    primary_index=defaultdict(list)
    for r in primary:
        primary_index[(str(r["date"]),r["league"],norm(r["home"]),norm(r["away"]))].append(r)
    cache={}
    used=set()
    confirmed=[]
    remaining=[]
    reasons=Counter()
    for batch in batches["batches"]:
        for fixture in batch["fixtures"]:
            league,season,day=(fixture[k] for k in ("league","season","date"))
            key=(day,league,norm(fixture["home"]),norm(fixture["away"]))
            original=primary_index.get(key,[])
            if len(original)!=1:
                reason="PRIMARY_MISSING_OR_AMBIGUOUS"
            else:
                if (season,league) not in cache:
                    rows,meta=secondary_rows(season,league,offline=offline)
                    index=defaultdict(list)
                    for r in rows:
                        index[(r["date"],league,norm(r["home"]),norm(r["away"]))].append(r)
                    cache[(season,league)]=(index,meta)
                index,meta=cache[(season,league)]
                matches=index.get(key,[])
                if meta.get("error"):
                    reason="SECONDARY_SOURCE_ERROR"
                elif len(matches)!=1:
                    reason="SECONDARY_MISSING_OR_AMBIGUOUS"
                elif (original[0]["hg"],original[0]["ag"])!=(matches[0]["home_goals"],matches[0]["away_goals"]):
                    reason="SCORE_CONFLICT"
                elif (season,key) in used:
                    reason="DUPLICATE_CLAIM"
                else:
                    used.add((season,key))
                    confirmed.append({"fixture":fixture,"score":[original[0]["hg"],original[0]["ag"]],
                        "secondary_provider":meta["provider"],"secondary_url":meta["url"],
                        "secondary_sha256":meta["sha256"],"verification":"EXACT_TEAM_DATE_SCORE_MATCH"})
                    continue
            reasons[reason]+=1
            remaining.append({"fixture":fixture,"reason":reason})
    return {"total":len(confirmed)+len(remaining),"confirmed":len(confirmed),
            "remaining":len(remaining),"reasons":dict(reasons),
            "verified":confirmed,"unresolved":remaining,"ex_final_allowed":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--batches",required=True)
    p.add_argument("--primary",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--offline")
    a=p.parse_args()
    result=reconcile(json.loads(Path(a.batches).read_text(encoding="utf-8")),load(a.primary),a.offline)
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("total","confirmed","remaining","reasons")},ensure_ascii=False))

if __name__=="__main__":
    main()
