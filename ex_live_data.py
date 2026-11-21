#!/usr/bin/env python3
"""EX data ingestion. Fails closed on stale, conflicting or unverified feeds."""
import argparse,csv,datetime as dt,hashlib,json,re,time,urllib.request,urllib.error
from pathlib import Path
from difflib import SequenceMatcher

LEAGUES={'en.1':'England Premier League','en.2':'England Championship','de.1':'Germany Bundesliga','de.2':'Germany Bundesliga 2','es.1':'Spain La Liga','it.1':'Italy Serie A','fr.1':'France Ligue 1','nl.1':'Netherlands Eredivisie','pt.1':'Portugal Primeira Liga','be.1':'Belgium First Division'}
FIELDS=['date','league','home','away','home_goals','away_goals','source','season']
def canonical(s):
 s=s.casefold().replace('&','and');return re.sub(r'[^a-z0-9]+','',s)
def aliases(path):
 if not path:return {}
 data=json.loads(Path(path).read_text(encoding='utf-8'))
 result={}
 for league,mapping in data.items():
  result[league]={canonical(alias):target for target,names in mapping.items() for alias in [target,*names]}
 return result
def team(s,league,alias):return alias.get(league,{}).get(canonical(s),s.strip())
def read_openfootball(blob,league,season,alias):
 data=json.loads(blob)
 if not isinstance(data,dict) or not isinstance(data.get('matches'),list):raise ValueError('invalid OpenFootball JSON')
 out=[];errors=[];fixtures=0
 for i,m in enumerate(data['matches']):
  try:
   day=dt.date.fromisoformat(m['date'][:10]);home=team(m['team1'],league,alias);away=team(m['team2'],league,alias)
   if not home or not away or canonical(home)==canonical(away):raise ValueError('invalid teams')
        score = m.get('score')
    if score is None:
     fixtures += 1
     continue
    if isinstance(score, list):
     ft = score
    elif isinstance(score, dict):
     ft = score.get('ft')
    else:
     raise ValueError('invalid score format')
   if ft is None:fixtures+=1;continue
   if not isinstance(ft,list) or len(ft)!=2 or any(not isinstance(x,int) or isinstance(x,bool) or x<0 or x>30 for x in ft):raise ValueError('invalid full-time score')
   out.append(dict(date=day.isoformat(),league=league,home=home,away=away,home_goals=ft[0],away_goals=ft[1],source='OpenFootball',season=season))
  except (KeyError,TypeError,ValueError) as e:errors.append({'index':i,'error':str(e)})
 return out,errors,fixtures

def fetch(url,retries=3,timeout=15):
 if not url.startswith('https://raw.githubusercontent.com/openfootball/football.json/') :raise ValueError('unapproved URL')
 for attempt in range(retries):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'EX-v4.3-data-integrity/1.0'})
   with urllib.request.urlopen(req,timeout=timeout) as resp:return resp.read()
  except (OSError,urllib.error.URLError):
   if attempt==retries-1:raise
   time.sleep(.5*(attempt+1))
def run(seasons,leagues,outdir,as_of,alias_file=None,offline=None,max_age_days=4):
 root=Path(outdir);root.mkdir(parents=True,exist_ok=True);alias=aliases(alias_file);rows=[];reports=[];keyed={};conflicts=[];rejected=[];seen_sources={}
 cutoff=dt.date.fromisoformat(as_of)
 for season in seasons:
  for league in leagues:
   if league not in LEAGUES:raise ValueError('unknown league '+league)
   url=f'https://raw.githubusercontent.com/openfootball/football.json/master/{season}/{league}.json'
   local=Path(offline)/season/(league+'.json') if offline else None
   try:
    raw=local.read_bytes() if local else fetch(url)
    digest=hashlib.sha256(raw).hexdigest();data,errors,fixtures=read_openfootball(raw,league,season,alias)
    if errors:rejected.extend([{'season':season,'league':league,**e} for e in errors])
    past=[r for r in data if r['date']<as_of]
    future_removed=len(data)-len(past)
    last=max((r['date'] for r in past),default=None)
    stale=not last or (cutoff-dt.date.fromisoformat(last)).days>max_age_days
    reports.append({'season':season,'league':league,'url':url,'sha256':digest,'rows_before_cutoff':len(past),'future_excluded':future_removed,'fixtures_without_score':fixtures,'last_result':last,'stale':stale,'errors':len(errors),'retrieval':'local_fixture' if local else 'https'})
    for r in past:
     k=(r['league'],r['date'],canonical(r['home']),canonical(r['away']))
     if k in keyed:
      old=keyed[k]
      if (old['home_goals'],old['away_goals'])!=(r['home_goals'],r['away_goals']):conflicts.append({'key':k,'a':old,'b':r})
     else:keyed[k]=r
   except (OSError,ValueError,KeyError,json.JSONDecodeError) as e:
    reports.append({'season':season,'league':league,'url':url,'error':str(e),'stale':True})
 rows=sorted(keyed.values(),key=lambda x:(x['date'],x['league'],x['home']))
 with (root/'results.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(rows)
 # OpenFootball is one provider. Multiple files are not independent confirmation.
 blocked=bool(conflicts or rejected or any(x.get('stale') for x in reports))
 status='BLOCKED' if blocked else 'INGESTED_SINGLE_PROVIDER_NOT_CROSS_VERIFIED'
 report={'status':status,'as_of_exclusive':as_of,'total_results':len(rows),'sources':reports,'conflicts':conflicts,'rejected_rows':rejected,'independent_sources_confirmed':0,'ex_final_allowed':False,'warning':'Single provider; freshness of last match is not proof of complete fixture coverage. Validate schedule and second independent provider before EX FINAL.'}
 (root/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--seasons',nargs='+',required=True);p.add_argument('--leagues',nargs='+',required=True);p.add_argument('--as-of',required=True);p.add_argument('--outdir',default='ex_data');p.add_argument('--aliases');p.add_argument('--offline');p.add_argument('--max-age-days',type=int,default=4);a=p.parse_args()
 report=run(a.seasons,a.leagues,a.outdir,a.as_of,a.aliases,a.offline,a.max_age_days)
 print(json.dumps({'status':report['status'],'rows':report['total_results'],'report':str(Path(a.outdir)/'audit.json')},ensure_ascii=False))
if __name__=='__main__':main()
