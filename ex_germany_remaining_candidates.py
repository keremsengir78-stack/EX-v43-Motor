"""Derive manual-review alias candidates from the remaining shadow mismatches."""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def derive(report):
    if report.get("ex_final_allowed") is not False or report.get("aliases_approved") is not False:
        raise ValueError("remaining evidence must be quarantined")
    fixtures=report.get("fixtures")
    if not isinstance(fixtures,list) or len(fixtures)!=report.get("unmatched_total"):
        raise ValueError("incomplete remaining evidence")
    pairs=defaultdict(lambda: {"dates":set(),"fixtures":0})
    for row in fixtures:
        options=row.get("secondary_shared_team_candidates",[])
        if len(options)!=1:
            continue
        other=options[0]
        if row["home"]==other.get("home") and row["away"]!=other.get("away"):
            p,s=row["away"],other["away"]
        elif row["away"]==other.get("away") and row["home"]!=other.get("home"):
            p,s=row["home"],other["home"]
        elif row["home"]!=other.get("home") and row["away"]!=other.get("away"):
            # Two-sided mismatch needs separate evidence; never infer either.
            continue
        else:
            continue
        key=(p,s)
        pairs[key]["fixtures"]+=1
        pairs[key]["dates"].add(row["date"])
    primary=defaultdict(set);secondary=defaultdict(set)
    for p,s in pairs:
        primary[p].add(s);secondary[s].add(p)
    candidates=[{"league":"de.1","primary_name":p,"secondary_name":s,
                 "supporting_fixtures":v["fixtures"],"distinct_dates":len(v["dates"]),
                 "mapping_conflict":len(primary[p])>1 or len(secondary[s])>1,
                 "review_status":"MANUAL_REVIEW_REQUIRED","auto_approved":False}
                for (p,s),v in sorted(pairs.items())]
    return {"candidates":candidates,"aliases_approved":False,"ex_final_allowed":False,
            "score_verified":False,"source":"remaining_shadow_fixture_diagnostics"}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--remaining",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    result=derive(json.loads(Path(a.remaining).read_text(encoding="utf-8")))
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
    print(f"Remaining alias candidates: {len(result['candidates'])}")


if __name__=="__main__":
    main()
