"""Prioritize non-German unmatched fixtures for independent source investigation."""
import argparse
import json
from pathlib import Path


PRIORITY={
    "SECONDARY_SAME_DAY_SHARED_TEAM":1,
    "SECONDARY_DATE_PRESENT_NO_TEAM_MATCH":2,
    "SECONDARY_DATE_EMPTY":3,
    "MISSING_SOURCE_PRESENCE_STATUS":4,
}


def build(summary, limit=100):
    if summary.get("ex_final_allowed") is not False:
        raise ValueError("EX FINAL must remain locked")
    if type(limit) is not int or limit<1:
        raise ValueError("invalid review limit")
    rows=[]
    seen=set()
    for group in summary.get("groups",[]):
        league=group["league"]
        if league=="de.1":
            continue
        fixtures=group.get("unmatched_details")
        if not isinstance(fixtures,list) or len(fixtures)!=group.get("unmatched_count"):
            raise ValueError("incomplete review group")
        for fixture in fixtures:
            status=fixture.get("source_presence_status","MISSING_SOURCE_PRESENCE_STATUS")
            key=(league,group["season"],fixture.get("date"),fixture.get("home"),fixture.get("away"))
            if key in seen:
                raise ValueError("duplicate fixture in review queue")
            seen.add(key)
            rows.append({"league":league,"season":group["season"],
                         "date":fixture.get("date"),"home":fixture.get("home"),
                         "away":fixture.get("away"),"reason":status,
                         "review_status":"REQUIRES_INDEPENDENT_SOURCE_REVIEW"})
    expected=summary.get("unmatched_total",0)-summary.get("germany_unmatched",0)
    if len(rows)!=expected:
        raise ValueError("unmatched count mismatch")
    rows.sort(key=lambda r:(PRIORITY.get(r["reason"],5),r["league"],
                            str(r["date"]),str(r["home"]),str(r["away"])))
    return {"total_review_queue":len(rows),"exported":min(limit,len(rows)),
            "queue_version":2,"sort_policy":"reason_league_date_team",
            "fixtures":rows[:limit],"truncated":len(rows)>limit,
            "aliases_approved":False,"score_verified":False,
            "ex_final_allowed":False}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--summary",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--limit",type=int,default=100)
    a=p.parse_args()
    result=build(json.loads(Path(a.summary).read_text(encoding="utf-8")),a.limit)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
    print(f"Independent review queue: {result['exported']} / {result['total_review_queue']}")


if __name__=="__main__":
    main()
