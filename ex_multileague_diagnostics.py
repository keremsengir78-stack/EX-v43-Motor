"""Lossless source-presence diagnostics for non-German review queues.

This report does not validate scores or approve aliases.
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def diagnose(summary):
    if summary.get("ex_final_allowed") is not False:
        raise ValueError("EX FINAL must remain blocked")
    groups=summary.get("groups")
    if not isinstance(groups,list):
        raise ValueError("missing review groups")
    totals=defaultdict(Counter)
    samples=defaultdict(list)
    for group in groups:
        league=group.get("league")
        if league=="de.1":
            continue
        rows=group.get("unmatched_details")
        if not isinstance(rows,list) or len(rows)!=group.get("unmatched_count"):
            raise ValueError("truncated review group")
        for row in rows:
            reason=row.get("source_presence_status","MISSING_SOURCE_PRESENCE_STATUS")
            if not isinstance(reason,str) or not reason:
                reason="MISSING_SOURCE_PRESENCE_STATUS"
            totals[league][reason]+=1
            if len(samples[(league,reason)])<3:
                samples[(league,reason)].append({
                    k:row.get(k) for k in ("date","home","away","reason")})
    count=sum(sum(c.values()) for c in totals.values())
    if count!=summary.get("unmatched_total",0)-summary.get("germany_unmatched",0):
        raise ValueError("unmatched source total mismatch")
    return {"unmatched_total":count,
            "by_league":{league:{"count":sum(counter.values()),
                "source_presence":dict(sorted(counter.items())),
                "samples":{status:samples[(league,status)] for status in sorted(counter)}}
                for league,counter in sorted(totals.items())},
            "score_verified":False,"aliases_approved":False,
            "ex_final_allowed":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--summary",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=diagnose(json.loads(Path(a.summary).read_text(encoding="utf-8")))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
    print(json.dumps({"unmatched_total":result["unmatched_total"],
                      "league_counts":{k:v["count"] for k,v in result["by_league"].items()}}))


if __name__=="__main__":
    main()
