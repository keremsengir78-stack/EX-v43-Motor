"""Capture domestic season scoreboards separately from UCL research."""
import datetime as dt
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from ex_espn_provider import ESPN_LEAGUES, fetch_espn_scoreboard

CUTOFF="2026-11-24"
def main():
    out=Path("ucl_research_output/domestic")
    out.mkdir(parents=True,exist_ok=True)
    start_day=dt.date(2025,1,1)
    cutoff=dt.date.fromisoformat(CUTOFF)
    days = [(start_day + dt.timedelta(days=offset)).isoformat()
            for offset in range((cutoff - start_day).days)]
    jobs = [(league, day) for league in ESPN_LEAGUES if league != "UCL"
            for day in days if league == "no.1" or day >= "2025-07-01"]
    def fetch(job):
        league,day=job
        try:
            rows,meta=fetch_espn_scoreboard(league,day,CUTOFF,evidence_dir=out)
            return {"league":league,**meta,"rows":rows}
        except (OSError,ValueError,KeyError) as exc:
            return {"league":league,"date":day,"error":str(exc),"rows":[]}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(fetch,jobs))
    (out/"report.json").write_text(json.dumps({"sources":results,"ex_final_allowed":False},ensure_ascii=False),encoding="utf-8")
    print("DOMESTIC_RESEARCH",json.dumps([{"league":league,"rows":sum(len(r["rows"]) for r in results if r["league"]==league),"errors":sum("error" in r for r in results if r["league"]==league),"truncated":sum(bool(r.get("potentially_truncated")) for r in results if r["league"]==league)} for league in ESPN_LEAGUES if league!="UCL"]))
    if any("error" in r or r.get("potentially_truncated") for r in results):
        raise SystemExit(1)
if __name__=="__main__":
    main()
