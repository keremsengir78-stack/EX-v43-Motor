"""Independent score corroboration from football-data.co.uk; never silently merge."""
import csv
import hashlib
import datetime as dt
import io
import json
import re
import urllib.request
import unicodedata
from pathlib import Path

MAX_SECONDARY_BYTES = 2_000_000

DIVISIONS = {"en.1":"E0","en.2":"E1","de.1":"D1","de.2":"D2",
             "es.1":"SP1","it.1":"I1","fr.1":"F1","nl.1":"N1",
             "pt.1":"P1","be.1":"B1"}

def norm(name):
    value=unicodedata.normalize("NFKD",name.casefold())
    value="".join(c for c in value if not unicodedata.combining(c))
    value=re.sub(r"\bfootball club\b","",value)
    value=re.sub(r"\bfc\b","",value)
    value=re.sub(r"\bafc\b","",value)
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
            matches=[s for s in srs if (
                reviewed_name(p["home"],p["league"],alias)==reviewed_name(s["home"],s["league"],alias)
                or reviewed_name(p["away"],p["league"],alias)==reviewed_name(s["away"],s["league"],alias)
            )]
            if len(matches)==1:
                s=matches[0]
                if reviewed_name(p["home"],p["league"],alias)!=reviewed_name(s["home"],s["league"],alias) or reviewed_name(p["away"],p["league"],alias)!=reviewed_name(s["away"],s["league"],alias):
                    suggestions.append({"date":key[0],"league":key[1],"primary":[p["home"],p["away"]],"secondary":[s["home"],s["away"]],"status":"REVIEW_REQUIRED","basis":"unique_date_and_opponent_candidate"})
    return suggestions

def secondary_rows(season, league, offline=None):
    if league not in DIVISIONS:
        return [], {"error":"unsupported league"}
    try:
        years=season.split("-")
        if (len(years) != 2 or len(years[0]) != 4 or len(years[1]) not in (2, 4)
                or any(not year.isascii() or not year.isdigit() for year in years)
                or (int(years[1]) if len(years[1]) == 4 else int(years[0][:2] + years[1])) != int(years[0]) + 1):
            raise ValueError("invalid season")
    except (AttributeError, TypeError, ValueError):
        return [], {"error":"invalid season","provider":"football-data.co.uk"}
    code=years[0][-2:]+years[1][-2:]
    url=f"https://www.football-data.co.uk/mmz4281/{code}/{DIVISIONS[league]}.csv"
    try:
        if offline:
            path = Path(offline)/f"{code}_{DIVISIONS[league]}.csv"
            if path.stat().st_size > MAX_SECONDARY_BYTES:
                raise ValueError("secondary CSV exceeds size limit")
            with path.open("rb") as stream:
                raw=stream.read(MAX_SECONDARY_BYTES + 1)
        else:
            with urllib.request.urlopen(
                urllib.request.Request(url,headers={"User-Agent":"EX-v43-research/1.0"}),
                timeout=20
            ) as response:
                raw=response.read(MAX_SECONDARY_BYTES + 1)
        if len(raw) > MAX_SECONDARY_BYTES:
            raise ValueError("secondary CSV exceeds size limit")
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
        return rows,{"url":url,"rows":len(rows),"provider":"football-data.co.uk",
                     "sha256":hashlib.sha256(raw).hexdigest(),"raw_bytes":len(raw),
                     "retrieved_at":dt.datetime.now(dt.timezone.utc).isoformat(),
                     "retrieval_mode":"offline" if offline else "https"}
    except (OSError,ValueError,UnicodeError) as exc:
        return [],{"url":url,"error":str(exc),"provider":"football-data.co.uk"}


def validate_third_results(rows, as_of):
    """Fail closed on malformed, conflicting or future-dated third-party scores."""
    cutoff=dt.date.fromisoformat(as_of)
    seen={}
    clean=[]
    for i,row in enumerate(rows):
        try:
            day=dt.date.fromisoformat(row["date"])
            league=row["league"].strip()
            home=row["home"].strip()
            away=row["away"].strip()
            hg=row["home_goals"]; ag=row["away_goals"]
            if type(hg) is not int or type(ag) is not int:
                raise ValueError("goals must be integers")
            if not league or not home or not away or norm(home)==norm(away):
                raise ValueError("invalid teams or league")
            if min(hg,ag)<0 or max(hg,ag)>30:
                raise ValueError("invalid goal range")
            if day>=cutoff:
                raise ValueError("result not before cutoff")
            key=(day.isoformat(),league,norm(home),norm(away))
            if key in seen:
                raise ValueError("duplicate third-source fixture")
            seen[key]=i
            clean.append({**row,"date":day.isoformat(),"league":league,
                          "home":home,"away":away,"home_goals":hg,"away_goals":ag})
        except (KeyError,TypeError,AttributeError) as exc:
            raise ValueError(f"invalid third-source row {i}: {exc}") from exc
        except ValueError as exc:
            raise ValueError(f"invalid third-source row {i}: {exc}") from exc
    if not clean:
        raise ValueError("empty third-source results")
    return clean

def validate_third_provenance(provider, reference):
    """Declared provenance gate; cannot establish actual independence by itself."""
    if not isinstance(provider,str) or not provider.strip():
        raise ValueError("third source provider missing")
    if provider.strip().casefold() in ("openfootball","football-data.co.uk","football data","football-data"):
        raise ValueError("third source duplicates a known provider")
    if not isinstance(reference,str) or not reference.startswith("https://"):
        raise ValueError("third source HTTPS reference missing")
    return {"provider":provider.strip(),"reference":reference,
            "provenance_status":"DECLARED_NOT_INDEPENDENTLY_AUDITED"}

def secondary_only_after_cutoff(secondary, primary_last, as_of):
    """Stage newer independent-provider scores; never merge them as verified results."""
    return [
        {"date":r["date"],"league":r["league"],"home":r["home"],
         "away":r["away"],"home_goals":r["home_goals"],"away_goals":r["away_goals"],
         "verification_status":"SECONDARY_ONLY_UNVERIFIED"}
        for r in secondary
        if r["date"]<as_of and (primary_last is None or r["date"]>primary_last)
    ]

def reconcile_staged_with_third(staged, third, as_of, alias=None):
    """Cross-check staged second-source rows against an independent third provider.

    This is a separate verification ledger, not an automatic history merge.
    """
    third_index={}
    for row in third:
        if row["date"]>=as_of: continue
        key=(row["date"],row["league"],reviewed_name(row["home"],row["league"],alias),
             reviewed_name(row["away"],row["league"],alias))
        third_index.setdefault(key,[]).append(row)
    verified=[]; conflicts=[]; unresolved=[]
    seen_staged=set()
    for row in staged:
        key=(row["date"],row["league"],reviewed_name(row["home"],row["league"],alias),
             reviewed_name(row["away"],row["league"],alias))
        if row["date"]>=as_of:
            unresolved.append({**row,"third_source_status":"AT_OR_AFTER_CUTOFF"})
            continue
        if key in seen_staged:
            unresolved.append({**row,"third_source_status":"DUPLICATE_STAGED_FIXTURE"})
            continue
        seen_staged.add(key)
        matches=third_index.get(key,[])
        if len(matches)!=1:
            unresolved.append({**row,"third_source_status":"MISSING" if not matches else "AMBIGUOUS",
                               **secondary_presence_diagnostic(row, third, as_of, alias)})
            continue
        other=matches[0]
        if (row["home_goals"],row["away_goals"])==(other["home_goals"],other["away_goals"]):
            verified.append({**row,"third_source_status":"SCORE_MATCH_PROVENANCE_UNAUDITED"})
        else:
            conflicts.append({**row,"third_source_status":"SCORE_CONFLICT",
                              "third_score":[other["home_goals"],other["away_goals"]]})
    return {"status":"NO_STAGED_RESULTS" if not staged else ("CONFLICT" if conflicts else ("PARTIAL" if unresolved else "PROVISIONAL_MATCH_UNAUDITED")),
            "verified":verified,"conflicts":conflicts,"unresolved":unresolved,
            "verified_count":len(verified),"conflict_count":len(conflicts),
            "unresolved_count":len(unresolved),"ex_final_allowed":False}

def secondary_presence_diagnostic(row, secondary, as_of, alias=None):
    """Describe secondary coverage without asserting a match or inventing aliases."""
    day_rows = [s for s in secondary
                if s["date"] == row["date"] and s["league"] == row["league"]
                and s["date"] < as_of]
    home = reviewed_name(row["home"], row["league"], alias)
    away = reviewed_name(row["away"], row["league"], alias)
    shared = [s for s in day_rows
              if reviewed_name(s["home"], s["league"], alias) == home
              or reviewed_name(s["away"], s["league"], alias) == away]
    exact_home = [s for s in day_rows
                  if reviewed_name(s["home"], s["league"], alias) == home]
    exact_away = [s for s in day_rows
                  if reviewed_name(s["away"], s["league"], alias) == away]
    reverse = [s for s in day_rows
               if reviewed_name(s["home"], s["league"], alias) == away
               and reviewed_name(s["away"], s["league"], alias) == home]
    near_day = []
    try:
        fixture_day = dt.date.fromisoformat(row["date"])
        for s in secondary:
            if s["league"] != row["league"] or s["date"] >= as_of:
                continue
            delta = (dt.date.fromisoformat(s["date"]) - fixture_day).days
            if abs(delta) != 1:
                continue
            if (reviewed_name(s["home"], s["league"], alias) == home
                    and reviewed_name(s["away"], s["league"], alias) == away):
                near_day.append({"date": s["date"], "home": s["home"],
                                 "away": s["away"], "day_offset": delta})
    except (ValueError, TypeError, KeyError):
        near_day = []
    return {
        "secondary_adjacent_day_exact_candidates": near_day[:5],
        "secondary_adjacent_day_exact_count": len(near_day),
        "secondary_home_team_count": len(exact_home),
        "secondary_away_team_count": len(exact_away),
        "secondary_reversed_fixture_count": len(reverse),
        "secondary_date_fixture_count": len(day_rows),
        "secondary_shared_team_count": len(shared),
        "source_presence_status": (
            "SECONDARY_DATE_EMPTY" if not day_rows else
            "SECONDARY_SAME_DAY_SHARED_TEAM" if shared else
            "SECONDARY_DATE_PRESENT_NO_TEAM_MATCH"
        ),
        "secondary_shared_team_candidates": [
            {"home": s["home"], "away": s["away"]} for s in shared[:5]
        ],
    }


def verify(primary, secondary, as_of, alias=None):
    index={}
    for row in secondary:
        if row["date"]>=as_of:continue
        key=(row["date"],row["league"],reviewed_name(row["home"],row["league"],alias),reviewed_name(row["away"],row["league"],alias))
        index.setdefault(key,[]).append(row)
    matched=0;conflicts=[];unmatched=0;ambiguous=0;unmatched_details=[]
    for row in primary:
        key=(row["date"],row["league"],reviewed_name(row["home"],row["league"],alias),reviewed_name(row["away"],row["league"],alias))
        candidates=index.get(key,[])
        if len(candidates)!=1:
            unmatched+=1
            unmatched_details.append({"date":row["date"],"league":row["league"],"home":row["home"],"away":row["away"],"reason":"ambiguous" if len(candidates)>1 else "not_found",
                **secondary_presence_diagnostic(row, secondary, as_of, alias)})
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
    return {"unmatched_details":unmatched_details,"alias_suggestions":suggestions[:100],"alias_suggestion_count":len(suggestions),"matched":matched,"unmatched":unmatched,"ambiguous":ambiguous,"conflicts":conflicts,
            "coverage":round(matched/len(primary),4) if primary else 0,
            "status":"CONFLICT" if conflicts else ("PARTIAL_VERIFICATION" if unmatched else "VERIFIED") if primary else "NO_PRIMARY_DATA"}
