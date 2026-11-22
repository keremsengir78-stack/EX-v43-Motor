"""Create review-only name candidates across non-German leagues from audit evidence."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def extract(summary):
    if summary.get("ex_final_allowed") is not False:
        raise ValueError("EX FINAL must remain locked")
    groups=summary.get("groups")
    if not isinstance(groups,list):
        raise ValueError("missing full review groups")
    pairs=defaultdict(lambda: {"dates":set(),"fixtures":0})
    counts=defaultdict(int)
    for group in groups:
        league=group["league"]
        if league=="de.1":
            continue
        rows=group["unmatched_details"]
        if len(rows)!=group["unmatched_count"]:
            raise ValueError("truncated review evidence")
        counts[league]+=len(rows)
        for row in rows:
            if row.get("source_presence_status")!="SECONDARY_SAME_DAY_SHARED_TEAM":
                continue
            for other in row.get("secondary_shared_team_candidates",[]):
                ph,pa=row["home"],row["away"]
                sh,sa=other["home"],other["away"]
                if ph==sh and pa!=sa:
                    p,s=pa,sa
                elif pa==sa and ph!=sh:
                    p,s=ph,sh
                else:
                    continue
                key=(league,p,s)
                pairs[key]["fixtures"]+=1
                pairs[key]["dates"].add(row["date"])
    forward=defaultdict(set);reverse=defaultdict(set)
    for league,p,s in pairs:
        forward[(league,p)].add(s)
        reverse[(league,s)].add(p)
    candidates=[{"league":league,"primary_name":p,"secondary_name":s,
                 "supporting_fixtures":v["fixtures"],"distinct_dates":len(v["dates"]),
                 "mapping_conflict":len(forward[(league,p)])>1 or len(reverse[(league,s)])>1,
                 "review_status":"MANUAL_REVIEW_REQUIRED","auto_approved":False}
                for (league,p,s),v in sorted(pairs.items())]
    expected=summary["unmatched_total"]-summary["germany_unmatched"]
    if sum(counts.values())!=expected:
        raise ValueError("non-German unmatched count mismatch")
    return {"unmatched_by_league":dict(sorted(counts.items())),
            "non_germany_unmatched":expected,"candidate_count":len(candidates),
            "candidates":candidates,"aliases_approved":False,
            "score_verified":False,"ex_final_allowed":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--summary",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=extract(json.loads(Path(a.summary).read_text(encoding="utf-8")))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
    print(json.dumps({"non_germany_unmatched":report["non_germany_unmatched"],
                      "candidate_count":report["candidate_count"]}))


if __name__=="__main__":
    main()
