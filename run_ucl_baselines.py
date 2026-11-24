"""Compute archive-backed cross-league research baselines, never EX FINAL."""
import json
from pathlib import Path
from ex_engine import date
from ex_ucl_baseline import cross_league_baseline
from ex_cross_verify import norm
from run_ucl_archive import full_time

def main():
    root=Path("ucl_research_output")
    rows=[]
    for path in sorted((root/"openfootball").glob("20*.json")):
        league=path.stem.split("_",1)[1]
        for m in json.loads(path.read_text()).get("matches",[]):
            score=full_time(m)
            if not isinstance(score,list) or len(score)!=2 or not all(type(v) is int and 0<=v<=30 for v in score): continue
            if not m.get("date") or m["date"]>="2026-11-24": continue
            rows.append(dict(date=date(m["date"]),league=league,home=m["team1"],away=m["team2"],hg=score[0],ag=score[1]))
    rows.sort(key=lambda r:r["date"])
    names={}
    for r in rows:
        for team in (r["home"],r["away"]):
            names.setdefault(norm(team),set()).add((r["league"],team))
    fixtures=json.loads(Path("config/ucl_matchday5_2026_research.json").read_text())["fixtures"]
    results=[]
    for f in fixtures:
        home=names.get(norm(f["home"]),set());away=names.get(norm(f["away"]),set())
        if len(home)!=1 or len(away)!=1:
            results.append({"fixture":f,"status":"BLOCKED_TEAM_MAPPING","home_candidates":sorted(home),"away_candidates":sorted(away),"ex_final_allowed":False})
            continue
        hl,hn=next(iter(home));al,an=next(iter(away))
        if hl=="no.1" or al=="no.1":
            results.append({"fixture":f,"status":"BLOCKED_CALENDAR_SEASON_MAPPING","ex_final_allowed":False})
            continue
        results.append(cross_league_baseline(rows,f,hl,al,hn,an,"2026-07-01","2025-07-01"))
    (root/"archive_baselines.json").write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print("UCL_BASELINE_COUNTS",json.dumps({"rows":len(rows),"fixtures":len(results),"computed":sum(r["status"]=="UNCALIBRATED_CROSS_LEAGUE_BASELINE" for r in results)}))
    for r in results:
        print("UCL_BASELINE_ROW",json.dumps({"fixture":r["fixture"],"status":r["status"],"samples":r.get("samples"),"baseline":r.get("baseline")},ensure_ascii=True))
if __name__=="__main__": main()
