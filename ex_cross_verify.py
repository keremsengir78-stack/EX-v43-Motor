"""Independent score corroboration from football-data.co.uk; never silently merge."""
import csv
import datetime as dt
import io
import json
import re
import urllib.request
from pathlib import Path

DIVISIONS = {"en.1":"E0","en.2":"E1","de.1":"D1","de.2":"D2",
             "es.1":"SP1","it.1":"I1","fr.1":"F1","nl.1":"N1",
             "pt.1":"P1","be.1":"B1"}

def norm(name):
    return re.sub(r"[^a-z0-9]+", "", name.casefold())

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

def verify(primary, secondary, as_of):
    index={}
    for row in secondary:
        if row["date"]>=as_of:continue
        key=(row["date"],row["league"],norm(row["home"]),norm(row["away"]))
        index.setdefault(key,[]).append(row)
    matched=0;conflicts=[];unmatched=0
    for row in primary:
        key=(row["date"],row["league"],norm(row["home"]),norm(row["away"]))
        candidates=index.get(key,[])
        if len(candidates)!=1:
            unmatched+=1
            continue
        matched+=1
        other=candidates[0]
        if (row["home_goals"],row["away_goals"])!=(other["home_goals"],other["away_goals"]):
            conflicts.append({"date":row["date"],"league":row["league"],
                              "home":row["home"],"away":row["away"],
                              "primary":[row["home_goals"],row["away_goals"]],
                              "secondary":[other["home_goals"],other["away_goals"]]})
    return {"matched":matched,"unmatched":unmatched,"conflicts":conflicts,
            "coverage":round(matched/len(primary),4) if primary else 0,
            "status":"CONFLICT" if conflicts else "PARTIAL_VERIFICATION"}
