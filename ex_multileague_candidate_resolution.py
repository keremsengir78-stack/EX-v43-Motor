"""Rank same-day source fixtures by both team names; never auto-approve scores."""
import argparse
import difflib
import json
from pathlib import Path
from ex_cross_verify import norm, secondary_rows

def candidates(batches, max_per_fixture=3, offline=None):
    if batches.get("ex_final_allowed") is not False or batches.get("independently_verified_added")!=0:
        raise ValueError("unsafe batch")
    cache={}
    output=[]
    for batch in batches["batches"]:
        for fixture in batch["fixtures"]:
            league=fixture["league"];season=fixture["season"]
            if (league,season) not in cache:
                rows,meta=secondary_rows(season,league,offline=offline)
                cache[(league,season)]=(rows,meta)
            rows,meta=cache[(league,season)]
            scored=[]
            for row in rows:
                if row["date"]!=fixture["date"]:continue
                home=difflib.SequenceMatcher(None,norm(fixture["home"]),norm(row["home"])).ratio()
                away=difflib.SequenceMatcher(None,norm(fixture["away"]),norm(row["away"])).ratio()
                score=round((home+away)/2,5)
                scored.append((score,home,away,row))
            scored.sort(key=lambda x:(-x[0],-x[1],-x[2],x[3]["home"],x[3]["away"]))
            output.append({"fixture":{k:fixture[k] for k in ("league","season","date","home","away")},
                           "source_provider":meta.get("provider"),
                           "source_url":meta.get("url"),"source_sha256":meta.get("sha256"),
                           "source_error":meta.get("error"),
                           "candidates":[{"home":r["home"],"away":r["away"],
                                          "home_goals":r["home_goals"],"away_goals":r["away_goals"],
                                          "name_similarity":score,
                                          "home_similarity":round(h,5),"away_similarity":round(a,5)}
                                         for score,h,a,r in scored[:max_per_fixture]],
                           "status":"REVIEW_REQUIRED","independent_score_verified":False})
    return {"total_fixtures":len(output),"with_candidates":sum(bool(r["candidates"]) for r in output),
            "without_candidates":sum(not r["candidates"] for r in output),
            "records":output,"independently_verified_added":0,"ex_final_allowed":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--batches",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--offline")
    a=p.parse_args()
    result=candidates(json.loads(Path(a.batches).read_text(encoding="utf-8")),offline=a.offline)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":main()
