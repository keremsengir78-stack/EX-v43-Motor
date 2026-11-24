"""Capture domestic season scoreboards separately from UCL research."""
import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from ex_espn_provider import ESPN_LEAGUES, parse_espn_scoreboard

CUTOFF="2026-11-24"
def main():
    out=Path("ucl_research_output/domestic")
    out.mkdir(parents=True,exist_ok=True)
    start_day=dt.date(2025,7,1)
    cutoff=dt.date.fromisoformat(CUTOFF)
    windows=[]
    while start_day<cutoff:
        end_day=min(start_day+dt.timedelta(days=27),cutoff-dt.timedelta(days=1))
        windows.append((start_day.strftime("%Y%m%d"),end_day.strftime("%Y%m%d")))
        start_day=end_day+dt.timedelta(days=1)
    jobs=[(league,start,end) for league in ESPN_LEAGUES if league!="UCL" for start,end in windows]
    def fetch(job):
        league,start,end=job
        url=f"https://site.api.espn.com/apis/site/v2/sports/soccer/{ESPN_LEAGUES[league]}/scoreboard?dates={start}-{end}&limit=100"
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"EX-v43-audit/1.0"}),timeout=40) as response:
                raw=response.read(30000001)
            if len(raw)>30000000:
                raise ValueError("response too large")
            payload=json.loads(raw)
            rows=parse_espn_scoreboard(payload,league,CUTOFF)
            digest=hashlib.sha256(raw).hexdigest()
            (out/(digest+".json")).write_bytes(raw)
            return {"league":league,"start":start,"end":end,"url":url,"sha256":digest,"rows":rows,"potentially_truncated":len(payload["events"])>=100,"retrieved_at":dt.datetime.now(dt.timezone.utc).isoformat()}
        except (OSError,ValueError,KeyError) as exc:
            return {"league":league,"start":start,"end":end,"error":str(exc),"rows":[]}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(fetch,jobs))
    (out/"report.json").write_text(json.dumps({"sources":results,"ex_final_allowed":False},ensure_ascii=False),encoding="utf-8")
    print("DOMESTIC_RESEARCH",json.dumps([{"league":league,"rows":sum(len(r["rows"]) for r in results if r["league"]==league),"errors":sum("error" in r for r in results if r["league"]==league),"truncated":sum(bool(r.get("potentially_truncated")) for r in results if r["league"]==league)} for league in ESPN_LEAGUES if league!="UCL"]))
    if any("error" in r or r.get("potentially_truncated") for r in results):
        raise SystemExit(1)
if __name__=="__main__":
    main()
