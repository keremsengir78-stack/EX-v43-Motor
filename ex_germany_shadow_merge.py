"""Combine two quarantined candidate reports for an isolated shadow test only."""
import argparse
import json
from pathlib import Path
from ex_germany_alias_pilot import build_pilot


def merge_candidates(first, second):
    if first.get("ex_final_allowed") is not False or second.get("ex_final_allowed") is not False:
        raise ValueError("candidate sources must block EX FINAL")
    if second.get("score_verified") is not False or second.get("aliases_approved") is not False:
        raise ValueError("remaining candidate report must be unverified")
    combined={"candidates":first.get("candidates",[])+second.get("candidates",[]),
              "ex_final_allowed":False,"aliases_approved":False,
              "score_verified":False,"comparison_only":True}
    # Reject any cross-report one-to-many conflicts before writing a map.
    build_pilot(combined)
    return combined


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--first",required=True)
    p.add_argument("--second",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    first=json.loads(Path(a.first).read_text(encoding="utf-8"))
    second=json.loads(Path(a.second).read_text(encoding="utf-8"))
    combined=merge_candidates(first,second)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(combined,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
    print(f"Shadow-only candidate pairs: {len(combined['candidates'])}")


if __name__=="__main__":
    main()
