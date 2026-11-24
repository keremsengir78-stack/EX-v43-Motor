"""Isolated UCL research ingestion; never publishes EX FINAL."""
import json
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from ex_espn_provider import fetch_espn_scoreboard

DAYS=["2026-09-08","2026-09-09","2026-09-10","2026-10-13","2026-10-14","2026-10-20","2026-10-21","2026-11-03","2026-11-04"]
def main():
    out=Path("ucl_research_output")
    out.mkdir(exist_ok=True)
    def fetch(day):
        try:
            rows,meta=fetch_espn_scoreboard("UCL",day,"2026-11-24",evidence_dir=out/"raw")
            return rows,meta,None
        except (OSError,ValueError,KeyError) as exc:
            return [],None,{"date":day,"error":str(exc)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        records=list(pool.map(fetch,DAYS))
    rows=[r for group,_,_ in records for r in group]
    counts=Counter(team for r in rows for team in (r["home"],r["away"]))
    errors=[e for _,_,e in records if e]
    report={"rows":rows,"requests":[m for _,m,_ in records if m],"errors":errors,"team_counts":dict(counts),"coverage_complete":len(rows)==72 and len(counts)==36 and all(n==4 for n in counts.values()) and not errors,"ex_final_allowed":False}
    (out/"report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print("UCL_RESEARCH",json.dumps({"rows":len(rows),"teams":len(counts),"complete":report["coverage_complete"],"errors":errors}))
    if not report["coverage_complete"]:
        raise SystemExit(1)
if __name__=="__main__":
    main()
