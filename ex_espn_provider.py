"""ESPN scoreboard adapter. Third-party scores remain provisional until provenance audited."""
import datetime as dt
import json
import hashlib
import urllib.request
import math

MAX_SCOREBOARD_BYTES=2_000_000

ESPN_LEAGUES={"en.1":"eng.1","en.2":"eng.2","de.1":"ger.1","de.2":"ger.2","es.1":"esp.1","it.1":"ita.1","fr.1":"fra.1","UCL":"uefa.champions","tr.1":"tur.1","nl.1":"ned.1","pt.1":"por.1","be.1":"bel.1","no.1":"nor.1","at.1":"aut.1","gr.1":"gre.1","sk.1":"svk.1","cz.1":"cze.1","ua.1":"ukr.1","az.1":"aze.1"}

def parse_espn_scoreboard(payload,league,as_of,requested_day=None):
    if league not in ESPN_LEAGUES:
        raise ValueError("unsupported ESPN league")
    cutoff=dt.date.fromisoformat(as_of)
    requested=dt.date.fromisoformat(requested_day) if requested_day is not None else None
    if requested is not None and requested>=cutoff:
        raise ValueError("requested date must precede cutoff")
    if not isinstance(payload,dict) or not isinstance(payload.get("events"),list):
        raise ValueError("invalid ESPN scoreboard response")
    out=[]
    seen={}
    for event in payload["events"]:
        if not isinstance(event,dict):
            continue
        competitions=event.get("competitions",[])
        if not isinstance(competitions,list) or not all(isinstance(x,dict) for x in competitions):
            continue
        if len(competitions)!=1:
            continue
        competitors=competitions[0].get("competitors",[])
        raw_status=event.get("status")
        status=raw_status.get("type") if isinstance(raw_status,dict) else None
        if not isinstance(status,dict) or not isinstance(competitors,list) or not all(isinstance(x,dict) for x in competitors):
            continue
        if status.get("completed") is not True or len(competitors)!=2:
            continue
        by_side={x.get("homeAway"):x for x in competitors}
        if len(by_side)!=2 or set(by_side)!={"home","away"}:
            continue
        try:
            raw_date=event["date"]
            if not isinstance(raw_date,str) or len(raw_date)<10:
                continue
            stamp=dt.datetime.fromisoformat(raw_date.replace("Z","+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset()!=dt.timedelta(0):
                continue
            day=stamp.date()
            if day>=cutoff or (requested is not None and day!=requested):
                continue
            home=by_side["home"];away=by_side["away"]
            home_name=home["team"]["displayName"].strip()
            away_name=away["team"]["displayName"].strip()
            if not home_name or not away_name or home_name.casefold()==away_name.casefold():
                continue
            raw_hg,raw_ag=home["score"],away["score"]
            if any(isinstance(v,bool) or not isinstance(v,(int,str)) or not str(v).isascii() or not str(v).isdigit() for v in (raw_hg,raw_ag)):
                continue
            hg=int(raw_hg);ag=int(raw_ag)
            if not home_name or not away_name or min(hg,ag)<0 or max(hg,ag)>30:
                continue
            key=(day.isoformat(),league,home_name.casefold(),away_name.casefold())
            score=(hg,ag)
            if key in seen:
                if seen[key]!=score:
                    raise ValueError("conflicting ESPN scores for duplicate fixture")
                continue
            seen[key]=score
            out.append({"date":day.isoformat(),"league":league,"home":home_name,
                        "away":away_name,"home_goals":hg,"away_goals":ag})
        except (KeyError,TypeError,AttributeError):
            continue
        except ValueError as exc:
            if str(exc) == "conflicting ESPN scores for duplicate fixture":
                raise
            continue
    return out

def fetch_espn_scoreboard(league,day,as_of,timeout=15,evidence_dir=None):
    if league not in ESPN_LEAGUES:
        raise ValueError("unsupported ESPN league")
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 0<timeout<=60:
        raise ValueError("invalid ESPN request timeout")
    requested=dt.date.fromisoformat(day)
    if requested>=dt.date.fromisoformat(as_of):
        raise ValueError("requested date must precede cutoff")
    code=ESPN_LEAGUES[league]
    url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}/scoreboard?dates={requested:%Y%m%d}"
    req=urllib.request.Request(url,headers={"User-Agent":"EX-v43-audit/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as response:
        raw=response.read(MAX_SCOREBOARD_BYTES+1)
    if len(raw)>MAX_SCOREBOARD_BYTES:
        raise ValueError("ESPN scoreboard response exceeds size limit")
    parsed=parse_espn_scoreboard(json.loads(raw),league,as_of,requested_day=day)
    if evidence_dir is not None:
        from pathlib import Path
        root=Path(evidence_dir)
        root.mkdir(parents=True,exist_ok=True)
        digest=hashlib.sha256(raw).hexdigest()
        (root/(digest+".json")).write_bytes(raw)
    return parsed,{"provider":"ESPN","url":url,"retrieved_at":dt.datetime.now(dt.timezone.utc).isoformat(),"date":day,"sha256":hashlib.sha256(raw).hexdigest(),"raw_bytes":len(raw)}
