"""Risk-weighted source investigation plan; no automatic alias or score approvals."""
import argparse
import json
from collections import Counter
from pathlib import Path

WEIGHTS={"SECONDARY_SAME_DAY_SHARED_TEAM":3,
         "SECONDARY_DATE_PRESENT_NO_TEAM_MATCH":2,
         "SECONDARY_DATE_EMPTY":1}

def plan(summary):
    if summary.get("ex_final_allowed") is not False:
        raise ValueError("EX FINAL lock missing")
    groups=summary.get("groups")
    if not isinstance(groups,list):
        raise ValueError("missing source groups")
    seen=set()
    totals=Counter()
    buckets=Counter()
    for group in groups:
        league=group.get("league")
        if league=="de.1" or league=="fr.1":
            continue
        if league not in ("en.1","es.1","it.1"):
            raise ValueError("unexpected post-shadow league")
        fixtures=group.get("unmatched_details")
        if not isinstance(fixtures,list) or len(fixtures)!=group.get("unmatched_count"):
            raise ValueError("truncated review group")
        for r in fixtures:
            key=(league,group.get("season"),r.get("date"),r.get("home"),r.get("away"))
            if key in seen:
                raise ValueError("duplicate fixture")
            seen.add(key)
            status=r.get("source_presence_status")
            if status not in WEIGHTS:
                raise ValueError("unclassified source presence")
            totals[league]+=1
            buckets[(league,status)]+=1
    expected=summary.get("unmatched_total",0)-summary.get("germany_unmatched",0)
    if sum(totals.values())!=expected:
        raise ValueError("source count mismatch")
    order=sorted(({"league":league,"reason":reason,"count":count,
                   "priority_score":count*WEIGHTS[reason],
                   "action":"CHECK_DATE_TEAM_MAPPING_AND_INDEPENDENT_FINAL_SCORE",
                   "auto_approved":False}
                  for (league,reason),count in buckets.items()),
                 key=lambda r:(-r["priority_score"],r["league"],r["reason"]))
    return {"total_unmatched":expected,"priority_buckets":order,
            "independently_verified_added":0,"aliases_approved":False,
            "ex_final_allowed":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--summary",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    report=plan(json.loads(Path(a.summary).read_text(encoding="utf-8")))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
    print(json.dumps({"unmatched":report["total_unmatched"],"buckets":len(report["priority_buckets"])}))

if __name__=="__main__":
    main()
