"""Parallel alternative domestic archive capture; research only."""
import json, hashlib, urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from ex_espn_provider import ESPN_LEAGUES
def main():
    out=Path("ucl_research_output/openfootball")
    out.mkdir(parents=True,exist_ok=True)
    jobs=[(season,league) for season in ("2025-26","2026-27") for league in ESPN_LEAGUES if league!="UCL"]
    def fetch(job):
        season,league=job
        url=f"https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{league}.json"
        try:
            with urllib.request.urlopen(url,timeout=20) as response:
                raw=response.read(5000001)
            if len(raw)>5000000: raise ValueError("oversize")
            data=json.loads(raw)
            matches=data.get("matches",[])
            if not isinstance(matches,list) or not matches: raise ValueError("missing matches")
            (out/f"{season}_{league}.json").write_bytes(raw)
            return {"season":season,"league":league,"url":url,"sha256":hashlib.sha256(raw).hexdigest(),"completed_before_cutoff":sum(isinstance(m.get("score",{}).get("ft"),list) and m.get("date","9999")<"2026-11-24" for m in matches)}
        except (OSError,ValueError,TypeError,AttributeError) as exc:
            return {"season":season,"league":league,"error":str(exc)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(fetch,jobs))
    (out/"manifest.json").write_text(json.dumps({"sources":results,"ex_final_allowed":False},indent=2))
    print("ARCHIVE_RESEARCH",json.dumps(results))
if __name__=="__main__": main()
