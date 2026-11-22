"""Compact measurable summary of real secondary-source candidate coverage."""
import argparse
import json
from collections import defaultdict
from pathlib import Path

def summarize(report):
    records=report.get("records")
    if not isinstance(records,list) or len(records)!=report.get("total_fixtures") or report.get("ex_final_allowed") is not False:
        raise ValueError("invalid candidate report")
    by_league=defaultdict(lambda:{"total":0,"same_day_candidates":0,"no_same_day_candidates":0,"high_name_similarity":0,"source_errors":0})
    for record in records:
        fixture=record["fixture"]
        league=fixture["league"]
        item=by_league[league]
        item["total"]+=1
        options=record.get("candidates")
        if not isinstance(options,list) or record.get("independent_score_verified") is not False:
            raise ValueError("unsafe candidate evidence")
        if record.get("source_error"):
            item["source_errors"]+=1
        if options:
            item["same_day_candidates"]+=1
            if options[0]["name_similarity"]>=0.90 and options[0]["home_similarity"]>=0.85 and options[0]["away_similarity"]>=0.85:
                item["high_name_similarity"]+=1
        else:
            item["no_same_day_candidates"]+=1
    return {"total_fixtures":len(records),"with_candidates":sum(x["same_day_candidates"] for x in by_league.values()),
            "without_candidates":sum(x["no_same_day_candidates"] for x in by_league.values()),
            "high_name_similarity_candidates":sum(x["high_name_similarity"] for x in by_league.values()),
            "by_league":dict(sorted(by_league.items())),"independently_verified_added":0,"ex_final_allowed":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidates",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=summarize(json.loads(Path(a.candidates).read_text(encoding="utf-8")))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":main()
