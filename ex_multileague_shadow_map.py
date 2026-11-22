"""Quarantined multi-league provider alias map, never reviewed evidence."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def build(report):
    if report.get("ex_final_allowed") is not False or report.get("score_verified") is not False or report.get("aliases_approved") is not False:
        raise ValueError("unverified candidate source required")
    maps=defaultdict(dict)
    reverse=defaultdict(dict)
    for item in report.get("candidates",[]):
        if item.get("mapping_conflict") is not False or item.get("auto_approved") is not False or item.get("review_status")!="MANUAL_REVIEW_REQUIRED":
            raise ValueError("unsafe alias candidate")
        league,p,s=item.get("league"),item.get("primary_name"),item.get("secondary_name")
        if not all(isinstance(v,str) and v.strip() for v in (league,p,s)):
            raise ValueError("invalid candidate identity")
        if s in maps[league] and maps[league][s]!=p:
            raise ValueError("secondary maps to two primary teams")
        if p in reverse[league] and reverse[league][p]!=s:
            raise ValueError("primary maps to two secondary teams")
        maps[league][s]=p
        reverse[league][p]=s
    return {k:dict(sorted(v.items())) for k,v in sorted(maps.items())}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--candidates",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=build(json.loads(Path(a.candidates).read_text(encoding="utf-8")))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
    print(json.dumps({k:len(v) for k,v in result.items()}))


if __name__=="__main__":
    main()
