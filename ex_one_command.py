#!/usr/bin/env python3
"""One-command auditable EX ingestion, prediction and retrospective evaluation."""
import argparse, json, csv, datetime as dt, hashlib
from pathlib import Path
from ex_live_data import run as ingest
from ex_engine import load, audit, backtest

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--as-of',required=True,help='ISO date; results strictly before this date')
 p.add_argument('--seasons',nargs='+',required=True)
 p.add_argument('--leagues',nargs='+',required=True)
 p.add_argument('--fixtures',help='CSV with date,league,home,away,season_start,previous_start')
 p.add_argument('--offline',help='Local OpenFootball mirror root, organized season/league.json')
 p.add_argument('--aliases',help='Reviewed alias map JSON')
 p.add_argument('--outdir',default='ex_run')
 p.add_argument('--max-age-days',type=int,default=7)
 a=p.parse_args(); out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
 ing=ingest(a.seasons,a.leagues,str(out),a.as_of,a.aliases,a.offline,a.max_age_days)
 rows=load(out/'results.csv')
 result={'engine':'EX v4.3 integrated research v1.1','as_of':a.as_of,'ingestion':ing,'backtest':backtest(rows),'matches':[],'ex_final_allowed':False,'status':'NO_EX_FINAL','reason':'External-factor and match-context features, independent source validation, calibrated EX-G and market odds not verified'}
 if a.fixtures:
  with open(a.fixtures,encoding='utf-8-sig',newline='') as f: fixtures=list(csv.DictReader(f))
  for fixture in fixtures:
   if fixture['date'] < a.as_of: raise ValueError('Historical fixture supplied: cannot present retrospective prediction as pre-match')
  result['matches']=audit(rows,fixtures)
  if ing['status']=='BLOCKED':result['reason']='Data integrity/freshness gate blocked; '+result['reason']
 (out/'full_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 print(json.dumps({'status':result['status'],'rows':len(rows),'fixtures':len(result['matches']),'backtest_n':result['backtest'].get('n',0),'report':str(out/'full_report.json')},ensure_ascii=False))
if __name__=='__main__':main()
