"""Strictly reconcile unresolved fixtures against primary and secondary scored rows.

No fuzzy aliases, no inferred scores. A match is accepted only when the
date, league, both normalized team names and both goals agree one-to-one.
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from ex_engine import load
from ex_cross_verify import norm, secondary_rows

# Exact, league-scoped identities; not fuzzy similarity or score-derived aliases.
CLUB_IDENTITIES = {
    "en.1": {
        "newcastleunited": "newcastle",
        "leedsunited": "leeds",
        "manchesterunited": "manunited",
        "manchestercity": "mancity",
        "tottenhamhotspur": "tottenham",
        "brightonhovealbion": "brighton",
        "wolverhamptonwanderers": "wolves",
        "westhamunited": "westham",
        "nottinghamforest": "nottmforest",
    },
    "es.1": {
        "rayovallecanodemadrid": "rayovallecano",
        "rcdmallorca": "mallorca",
        "rcdespanyoldebarcelona": "espanyol",
        "rcceltadevigo": "celta",
        "deportivoalaves": "alaves",
        "realsociedaddefutbol": "realsociedad",
        "clubatleticodemadrid": "atleticomadrid",
        "athleticclub": "athbilbao",
        "athleticbilbao": "athbilbao",
    },
    "it.1": {
        "internazionalemilano": "inter",
        "juventus": "juventus",
        "parmacalcio1913": "parma",
        "fiorentina": "fiorentina",
        "acffiorentina": "fiorentina",
        "atalanta": "atalanta",
        "genoacfc": "genoa",
        "torino": "torino",
        "hellasverona": "verona",
        "lazio": "lazio",
        "sslazio": "lazio",
        "napoli": "napoli",
        "sscnapoli": "napoli",
        "bologna1909": "bologna",
        "udinesecalcio": "udinese",
        "cremonese": "cremonese",
        "uscremonese": "cremonese",
        "pisa1909": "pisa",
        "acpisa1909": "pisa",
        "como1907": "como",
    },
}

def club_norm(name, league=None):
    """Remove only standalone club-form suffixes, never fuzzy-match identities."""
    key=norm(re.sub(r"\b(?:cf|ud|ca)\b", " ", name, flags=re.IGNORECASE))
    return CLUB_IDENTITIES.get(league, {}).get(key, key)


def reconcile(batches, primary, offline=None):
    if batches.get("ex_final_allowed") is not False:
        raise ValueError("unsafe review batches")
    primary_index=defaultdict(list)
    for r in primary:
        primary_index[(r["season"],str(r["date"]),r["league"],club_norm(r["home"],r["league"]),club_norm(r["away"],r["league"]))].append(r)
    cache={}
    used=set()
    confirmed=[]
    remaining=[]
    reasons=Counter()
    for batch in batches["batches"]:
        for fixture in batch["fixtures"]:
            league,season,day=(fixture[k] for k in ("league","season","date"))
            key=(season,day,league,club_norm(fixture["home"],league),club_norm(fixture["away"],league))
            original=primary_index.get(key,[])
            if len(original)!=1:
                reason="PRIMARY_MISSING_OR_AMBIGUOUS"
            else:
                if (season,league) not in cache:
                    rows,meta=secondary_rows(season,league,offline=offline)
                    index=defaultdict(list)
                    for r in rows:
                        index[(season,r["date"],league,club_norm(r["home"],r["league"]),club_norm(r["away"],r["league"]))].append(r)
                    cache[(season,league)]=(index,meta)
                index,meta=cache[(season,league)]
                matches=index.get(key,[])
                if meta.get("error"):
                    reason="SECONDARY_SOURCE_ERROR"
                elif len(matches)!=1:
                    reason="SECONDARY_MISSING_OR_AMBIGUOUS"
                elif (original[0]["hg"],original[0]["ag"])!=(matches[0]["home_goals"],matches[0]["away_goals"]):
                    reason="SCORE_CONFLICT"
                elif key in used:
                    reason="DUPLICATE_CLAIM"
                else:
                    used.add(key)
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
