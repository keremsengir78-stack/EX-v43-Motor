#!/usr/bin/env python3
"""One-command auditable EX ingestion, prediction and retrospective evaluation."""
import argparse, json, csv, datetime as dt, hashlib
from pathlib import Path
from ex_live_data import run as ingest
from ex_engine import load, audit, backtest
from ex_cross_verify import secondary_rows, verify, norm, secondary_only_after_cutoff, reconcile_staged_with_third, validate_third_provenance, validate_third_results
from ex_decision import assess_markets
from ex_fixture_odds import check_fixture, check_odds
from ex_auto_control import auto_control
from ex_espn_provider import fetch_espn_scoreboard

def evidence_cutoff(as_of):
 """Use the exclusive start-of-day cutoff; never ingest same-day evidence."""
 day=dt.date.fromisoformat(as_of)
 if day.isoformat()!=as_of:
  raise ValueError('as_of must be YYYY-MM-DD')
 return day.isoformat()

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
 p.add_argument('--espn-third-source',action='store_true',help='Fetch ESPN completed results for dates of staged matches; provisional evidence only')
 p.add_argument('--third-source-csv',help='Independent third-provider results with date,league,home,away,home_goals,away_goals; manual or offline evidence only')
 p.add_argument('--third-source-provider',help='Name of independently identified third data provider')
 p.add_argument('--third-source-reference',help='Verifiable URL or reference for third-provider provenance')
 p.add_argument('--evidence',help='Verified market evidence JSON; remains uncalibrated')
 p.add_argument('--odds',help='JSON list of timestamped odds snapshots matching fixtures by order')
 a=p.parse_args(); out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
 ing=ingest(a.seasons,a.leagues,str(out),a.as_of,a.aliases,a.offline,a.max_age_days)
 rows=load(out/'results.csv')
 secondary_audits=[]
 secondary_only_staged=[]
 reviewed_aliases={}
 if a.secondary_aliases:
  alias_data=json.loads(Path(a.secondary_aliases).read_text(encoding='utf-8'))
  reviewed_aliases={league:{norm(k):v for k,v in names.items()} for league,names in alias_data.items()}
 if not a.no_secondary:
  for season in a.seasons:
   for league in a.leagues:
    candidates,meta=secondary_rows(season,league,a.secondary_offline)
    subset=[r for r in rows if r['season']==season and r['league']==league]
    primary_last=max((str(r['date']) for r in subset),default=None)
    secondary_last=max((r['date'] for r in candidates if r['date']<a.as_of),default=None)
    check=verify([{'date':str(r['date']),'league':r['league'],'home':r['home'],
                   'away':r['away'],'home_goals':r['hg'],'away_goals':r['ag']} for r in subset],
                 candidates,a.as_of,reviewed_aliases)
    staged=secondary_only_after_cutoff(candidates,primary_last,a.as_of)
    secondary_only_staged.extend([{'season':season,**r} for r in staged])
    secondary_only_recent=len(staged)
    secondary_audits.append({'season':season,'league':league,'source':meta,'comparison':check,'primary_last_result':primary_last,'secondary_last_result':secondary_last,'secondary_newer_than_primary':bool(secondary_last and primary_last and secondary_last>primary_last),'secondary_results_after_primary_cutoff':secondary_only_recent})
 (out/'secondary_only_unverified.json').write_text(json.dumps(secondary_only_staged,ensure_ascii=False,indent=2),encoding='utf-8')
 ing['secondary_only_staging_file']='secondary_only_unverified.json'
 if a.espn_third_source and a.third_source_csv:
  raise ValueError('Choose ESPN or CSV third source, not both')
 if a.espn_third_source:
  third=[]; source_metadata=[]; errors=[]
  dates=sorted({(r['league'],r['date']) for r in secondary_only_staged})
  from concurrent.futures import ThreadPoolExecutor
  def fetch_date(pair):
   league,day=pair
   try:
    found,metadata=fetch_espn_scoreboard(league,day,a.as_of)
    return found,metadata,None
   except (OSError,ValueError,KeyError) as exc:
    return [],None,{'league':league,'date':day,'error':str(exc)}
  # map preserves sorted request order; cap simultaneous provider requests.
  with ThreadPoolExecutor(max_workers=4) as pool:
   for found,metadata,error in pool.map(fetch_date,dates):
    third.extend(found)
    if metadata is not None:
     source_metadata.append(metadata)
    if error is not None:
     errors.append(error)
  if third:
   clean=validate_third_results(third,a.as_of)
   reconciliation=reconcile_staged_with_third(secondary_only_staged,clean,a.as_of,reviewed_aliases)
   (out/'third_source_reconciliation.json').write_text(json.dumps(reconciliation,ensure_ascii=False,indent=2),encoding='utf-8')
   ing['third_source_reconciliation']={**{k:v for k,v in reconciliation.items() if k not in ('verified','unresolved','conflicts')},'provider':'ESPN','source_requests':source_metadata,'source_errors':errors,'requested_dates':len(dates),'successful_requests':len(source_metadata),'provisional_coverage':round(reconciliation['verified_count']/len(secondary_only_staged),4) if secondary_only_staged else 0,'provenance_status':'AUTOMATIC_FETCH_NOT_INDEPENDENTLY_AUDITED'}
   (out/'espn_source_manifest.json').write_text(json.dumps({'requests':source_metadata,'errors':errors,'as_of':a.as_of,'staged_matches':len(secondary_only_staged),'ex_final_allowed':False},ensure_ascii=False,indent=2),encoding='utf-8')
  else:
   ing['third_source_reconciliation']={'status':'NO_RESULTS','verified_count':0,'source_errors':errors,'requested_dates':len(dates),'successful_requests':len(source_metadata),'provisional_coverage':0,'ex_final_allowed':False}
 elif a.third_source_csv:
  provenance=validate_third_provenance(a.third_source_provider,a.third_source_reference)
  third_sha256=hashlib.sha256(Path(a.third_source_csv).read_bytes()).hexdigest()
  with open(a.third_source_csv,encoding='utf-8-sig',newline='') as source:
   third=list(csv.DictReader(source))
  required={'date','league','home','away','home_goals','away_goals'}
  if not third or any(not required.issubset(r) for r in third):
   raise ValueError('Third source CSV missing required columns or records')
  clean=[]
  for r in third:
   try:
    hg=int(r['home_goals']);ag=int(r['away_goals'])
    dt.date.fromisoformat(r['date'])
    if hg<0 or ag<0 or not r['home'] or not r['away']:raise ValueError()
   except (ValueError,TypeError,KeyError):
    raise ValueError('Invalid third-source result')
   clean.append({**r,'home_goals':hg,'away_goals':ag})
  clean=validate_third_results(clean,a.as_of)
  reconciliation=reconcile_staged_with_third(secondary_only_staged,clean,a.as_of,reviewed_aliases)
  ing['third_source_reconciliation']={**{k:v for k,v in reconciliation.items() if k not in ('verified','unresolved','conflicts')},**provenance,'sha256':third_sha256}
  (out/'third_source_reconciliation.json').write_text(json.dumps(reconciliation,ensure_ascii=False,indent=2),encoding='utf-8')
 else:
  ing['third_source_reconciliation']={'status':'NOT_PROVIDED','verified_count':0,'ex_final_allowed':False}
 ing['secondary_audits']=secondary_audits
 ing['independent_sources_confirmed']=sum(1 for x in secondary_audits if x['comparison']['status']=='VERIFIED')
 ing['independent_matches_confirmed']=sum(x['comparison']['matched']-len(x['comparison']['conflicts']) for x in secondary_audits)
 ing['independent_source_coverage']={f"{x['season']}/{x['league']}":x['comparison']['coverage'] for x in secondary_audits}
 ing['secondary_conflicts']=sum(len(x['comparison']['conflicts']) for x in secondary_audits)
 ing['secondary_newer_unverified_results']=sum(x['secondary_results_after_primary_cutoff'] for x in secondary_audits)
 ing['secondary_alias_suggestions']=sum(x['comparison']['alias_suggestion_count'] for x in secondary_audits)
 ing['secondary_review_queue']=[{'season':x['season'],'league':x['league'],'suggestions':x['comparison']['alias_suggestions'],'unmatched':x['comparison']['unmatched_details']} for x in secondary_audits if x['comparison']['unmatched']]
 ing['secondary_unmatched_by_season']={f"{x['season']}/{x['league']}":x['comparison']['unmatched'] for x in secondary_audits}
 (out/'alias_review.json').write_text(json.dumps(ing['secondary_review_queue'],ensure_ascii=False,indent=2),encoding='utf-8')
 ing['secondary_unverified']=sum(x['comparison']['unmatched'] for x in secondary_audits)
 ing['secondary_source_errors']=[{'season':x['season'],'league':x['league'],'error':x['source']['error']} for x in secondary_audits if x['source'].get('error')]
 ing['source_coverage_warning']='Unmatched names require review; newer secondary-only results are NOT automatically merged or independently confirmed.'
 if ing['secondary_unverified'] or ing['secondary_source_errors'] or not secondary_audits:
  ing['status']='BLOCKED'
  ing['blocking_sources'].append({'reason':'incomplete_independent_verification','unmatched':ing['secondary_unverified']})
 if ing['secondary_newer_unverified_results']:
  ing['status']='BLOCKED'
  ing['blocking_sources'].append({'reason':'secondary_newer_results_not_independently_verified',
                                  'count':ing['secondary_newer_unverified_results'],
                                  'staging_file':'secondary_only_unverified.json'})
 if ing['secondary_conflicts']:
  ing['status']='BLOCKED'
  ing['blocking_sources'].append({'reason':'independent_source_score_conflict'})
 (out/'audit.json').write_text(json.dumps(ing,ensure_ascii=False,indent=2),encoding='utf-8')
 result={'engine':'EX v4.3 integrated research v1.1','as_of':a.as_of,'ingestion':ing,'backtest':backtest(rows),'matches':[],'ex_final_allowed':False,'status':'NO_EX_FINAL','reason':'External-factor and match-context features, independent source validation, calibrated EX-G and market odds not verified'}
 if a.evidence:
  evidence=json.loads(Path(a.evidence).read_text(encoding='utf-8'))
  result['decision_evidence']=assess_markets(evidence,as_of=evidence_cutoff(a.as_of))
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
   kickoff=fixtures[i].get('kickoff_at','')
   match['odds_lock']=check_odds(odds[i] if odds else None,kickoff) if kickoff else {'status':'BLOCKED','issues':['kickoff_at:missing'],'decision':'NO_FINAL','ex_final_allowed':False}
   match['decision']='NO_FINAL'
   match['auto_control']=auto_control(match,ing)

  if ing['status']=='BLOCKED':result['reason']='Data integrity/freshness gate blocked; '+result['reason']
 (out/'full_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
 print(json.dumps({'status':result['status'],'rows':len(rows),'fixtures':len(result['matches']),'backtest_n':result['backtest'].get('n',0),'report':str(out/'full_report.json')},ensure_ascii=False))
if __name__=='__main__':main()
