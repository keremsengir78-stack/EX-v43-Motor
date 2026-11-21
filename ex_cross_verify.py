"""Independent score corroboration from football-data.co.uk; never silently merge."""
import csv
import datetime as dt
import io
import json
import re
import urllib.request
import unicodedata
from pathlib import Path

DIVISIONS = {"en.1":"E0","en.2":"E1","de.1":"D1","de.2":"D2",
             "es.1":"SP1","it.1":"I1","fr.1":"F1","nl.1":"N1",
             "pt.1":"P1","be.1":"B1"}

def norm(name):
    value=unicodedata.normalize("NFKD",name.casefold())
    value="".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+","",value)

def reviewed_name(name, league, alias=None):
    key=norm(name)
    mapping=(alias or {}).get(league,{})
    return norm(mapping.get(key,name))

def unresolved_pairs(primary, secondary, as_of, alias=None):
    """Candidate name pairs by unique date + opponent, never auto-approved."""
    primary_by_date={}
    secondary_by_date={}
    for source, target in ((primary,primary_by_date),(secondary,secondary_by_date)):
        for r in source:
            if r["date"]>=as_of:continue
            target.setdefault((r["date"],r["league"]),[]).append(r)
    suggestions=[]
    for key,prs in primary_by_date.items():
        srs=secondary_by_date.get(key,[])
        for p in prs:
            matches=[s for s in srs if reviewed_name(p["home"],p["league"],alias)==reviewed_name(s["home"],s["league"],alias) or reviewed_name(p["away"],p["league"],alias)==reviewed_name(s["away"],s["league"],alias)]
            if len(matches)==1:
                s=matches[0]
                if reviewed_name(p["home"],p["league"],alias)!=reviewed_name(s["home"],s["league"],alias) or reviewed_name(p["away"],p["league"],alias)!=reviewed_name(s["away"],s["league"],alias):
                    suggestions.append({"date":key[0],"league":key[1],"primary":[p["home"],p["away"]],"secondary":[s["home"],s["away"]],"status":"REVIEW_REQUIRED"})
    return suggestions

def secondary_rows(season, league, offline=None):
    if league not in DIVISIONS:
        return [], {"error":"unsupported league"}
    years=season.split("-")
    code=years[0][-2:]+years[1][-2:]
    url=f"https://www.football-data.co.uk/mmz4281/{code}/{DIVISIONS[league]}.csv"
    try:
        if offline:
            raw=(Path(offline)/f"{code}_{DIVISIONS[league]}.csv").read_bytes()
        else:
            with urllib.request.urlopen(
                urllib.request.Request(url,headers={"User-Agent":"EX-v43-research/1.0"}),
                timeout=20
            ) as response:
                raw=response.read()
        parsed=list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        rows=[]
        for item in parsed:
            try:
                date=dt.datetime.strptime(item["Date"],"%d/%m/%Y").date()
            except (ValueError,TypeError):
                try:
                    date=dt.datetime.strptime(item["Date"],"%d/%m/%y").date()
                except (ValueError,TypeError,KeyError):
                    continue
            try:
                hg=int(item["FTHG"]);ag=int(item["FTAG"])
                home=item["HomeTeam"].strip();away=item["AwayTeam"].strip()
                if min(hg,ag)<0 or not home or not away:continue
            except (ValueError,TypeError,KeyError,AttributeError):
                continue
            rows.append({"date":date.isoformat(),"league":league,
                         "home":home,"away":away,"home_goals":hg,"away_goals":ag})
        return rows,{"url":url,"rows":len(rows),"provider":"football-data.co.uk"}
    except (OSError,ValueError,UnicodeError) as exc:
        return [],{"url":url,"error":str(exc),"provider":"football-data.co.uk"}

def verify(primary, secondary, as_of, alias=None):
    index={}
    for row in secondary:
        if row["date"]>=as_of:continue
        key=(row["date"],row["league"],reviewed_name(row["home"],row["league"],alias),reviewed_name(row["away"],row["league"],alias))
        index.setdefault(key,[]).append(row)
    matched=0;conflicts=[];unmatched=0;ambiguous=0
    for row in primary:
        key=(row["date"],row["league"],norm(row["home"]),norm(row["away"]))
        candidates=index.get(key,[])
        if len(candidates)!=1:
            unmatched+=1
            if len(candidates)>1:ambiguous+=1
            continue
        matched+=1
        other=candidates[0]
        if (row["home_goals"],row["away_goals"])!=(other["home_goals"],other["away_goals"]):
            conflicts.append({"date":row["date"],"league":row["league"],
                              "home":row["home"],"away":row["away"],
                              "primary":[row["home_goals"],row["away_goals"]],
                              "secondary":[other["home_goals"],other["away_goals"]]})
    suggestions=unresolved_pairs(primary,secondary,as_of,alias)
    return {"alias_suggestions":suggestions[:100],"alias_suggestion_count":len(suggestions),"matched":matched,"unmatched":unmatched,"ambiguous":ambiguous,"conflicts":conflicts,
            "coverage":round(matched/len(primary),4) if primary else 0,
            "status":"CONFLICT" if conflicts else ("PARTIAL_VERIFICATION" if unmatched else "VERIFIED") if primary else "NO_PRIMARY_DATA"}
