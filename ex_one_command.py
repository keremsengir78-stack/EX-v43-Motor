#!/usr/bin/env python3
"""One-command auditable EX ingestion, prediction and retrospective evaluation."""
import argparse, json, csv, datetime as dt, hashlib
from pathlib import Path
from ex_live_data import run as ingest
from ex_engine import load, audit, backtest
from ex_cross_verify import secondary_rows, verify, norm
from ex_decision import assess_markets
from ex_fixture_odds import check_fixture, check_odds
from ex_auto_control import auto_control

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
 p.add_argument('--secondary-offline',help='Directory with Football-Data CSV files')
 p.add_argument('--no-secondary',action='store_true')
 p.add_argument('--secondary-aliases',help='Reviewed cross-provider team aliases JSON')
 p.add_argument('--evidence',help='Verified market evidence JSON; remains uncalibrated')
 p.add_argument('--odds',help='JSON list of timestamped odds snapshots matching fixtures by order')
 a=p.parse_args(); out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
 ing=ingest(a.seasons,a.leagues,str(out),a.as_of,a.aliases,a.offline,a.max_age_days)
 rows=load(out/'results.csv')
 secondary_audits=[]
 reviewed_aliases={}
 if a.secondary_aliases:
  alias_data=json.loads(Path(a.secondary_aliases).read_text(encoding='utf-8'))
  reviewed_aliases={league:{norm(k):v for k,v in names.items()} for league,names in alias_data.items()}
 if not a.no_secondary:
  for season in a.seasons:
   for league in a.leagues:
    candidates,meta=secondary_rows(season,league,a.secondary_offline)
    subset=[r for r in rows if r['season']==season and r['league']==league]
    check=verify([{'date':str(r['date']),'league':r['league'],'home':r['home'],
                   'away':r['away'],'home_goals':r['hg'],'away_goals':r['ag']} for r in subset],
                 candidates,a.as_of,reviewed_aliases)
    secondary_audits.append({'season':season,'league':league,'source':meta,'comparison':check})
 ing['secondary_audits']=secondary_audits
 ing['independent_sources_confirmed']=sum(1 for x in secondary_audits if x['comparison']['status']=='VERIFIED')
 ing['independent_matches_confirmed']=sum(x['comparison']['matched']-len(x['comparison']['conflicts']) for x in secondary_audits)
 ing['independent_source_coverage']={f"{x['season']}/{x['league']}":x['comparison']['coverage'] for x in secondary_audits}
 ing['secondary_conflicts']=sum(len(x['comparison']['conflicts']) for x in secondary_audits)
 ing['secondary_alias_suggestions']=sum(x['comparison']['alias_suggestion_count'] for x in secondary_audits)
 ing['secondary_review_queue']=[{'season':x['season'],'league':x['league'],'suggestions':x['comparison']['alias_suggestions']} for x in secondary_audits if x['comparison']['alias_suggestion_count']]
 (out/'alias_review.json').write_text(json.dumps(ing['secondary_review_queue'],ensure_ascii=False,indent=2),encoding='utf-8')
 ing['secondary_unverified']=sum(x['comparison']['unmatched'] for x in secondary_audits)
 ing['secondary_source_errors']=[{'season':x['season'],'league':x['league'],'error':x['source']['error']} for x in secondary_audits if x['source'].get('error')]
 ing['source_coverage_warning']='Exact team-name matching can undercount valid matches; review aliases before treating unmatched records as score conflicts.'
 if ing['secondary_unverified'] or ing['secondary_source_errors'] or not secondary_audits:
  ing['status']='BLOCKED'
  ing['blocking_sources'].append({'reason':'incomplete_independent_verification','unmatched':ing['secondary_unverified']})
 if ing['secondary_conflicts']:
  ing['status']='BLOCKED'
  ing['blocking_sources'].append({'reason':'independent_source_score_conflict'})
 (out/'audit.json').write_text(json.dumps(ing,ensure_ascii=False,indent=2),encoding='utf-8')
 result={'engine':'EX v4.3 integrated research v1.1','as_of':a.as_of,'ingestion':ing,'backtest':backtest(rows),'matches':[],'ex_final_allowed':False,'status':'NO_EX_FINAL','reason':'External-factor and match-context features, independent source validation, calibrated EX-G and market odds not verified'}
 if a.evidence:
  evidence=json.loads(Path(a.evidence).read_text(encoding='utf-8'))
  result['decision_evidence']=assess_markets(evidence)
 if a.fixtures:
  with open(a.fixtures,encoding='utf-8-sig',newline='') as f: fixtures=list(csv.DictReader(f))
  for fixture in fixtures:
   if fixture['date'] < a.as_of: raise ValueError('Historical fixture supplied: cannot present retrospective prediction as pre-match')
  result['matches']=audit(rows,fixtures)
  odds=[]
  if a.odds:
   odds=json.loads(Path(a.odds).read_text(encoding='utf-8'))
   if not isinstance(odds,list) or len(odds)!=len(fixtures):
    raise ValueError('Odds snapshots must be a list matching fixture count')
  for i,match in enumerate(result['matches']):
   match['fixture_lock']=check_fixture(fixtures[i],a.as_of)
   match['odds_lock']=check_odds(odds[i] if odds else None,a.as_of+'T23:59:59+00:00')
   match['decision']='NO_FINAL'
   match['auto_control']=auto_control(match,ing)

  if ing['status']=='BLOCKED':result['reason']='Data integrity/freshness gate blocked; '+result['reason']
 (out/'full_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 print(json.dumps({'status':result['status'],'rows':len(rows),'fixtures':len(result['matches']),'backtest_n':result['backtest'].get('n',0),'report':str(out/'full_report.json')},ensure_ascii=False))
if __name__=='__main__':main()
