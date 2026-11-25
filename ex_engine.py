#!/usr/bin/env python3
"""EX v4.3 auditable offline goals model. Standard library only."""
import argparse,csv,datetime as dt,json,math,hashlib,statistics
from pathlib import Path
from ex_baseline_calibration import chronological_intercept
from ex_historical_features import HistoricalFeatures
from ex_leagues import season_bounds
W=(.4,.3,.2,.1)
REQUIRED=('date','league','home','away','home_goals','away_goals')
def date(s): return dt.date.fromisoformat(s)
def load(path):
    with open(path,encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    out=[]; seen=set()
    for i,r in enumerate(rows,2):
        if not all(r.get(k,'').strip() for k in REQUIRED): raise ValueError(f'{path}:{i} missing fields')
        try: d=date(r['date']); h=int(r['home_goals']); a=int(r['away_goals'])
        except Exception as e: raise ValueError(f'{path}:{i} invalid date/goals: {e}')
        if h<0 or a<0 or h>30 or a>30: raise ValueError(f'{path}:{i} invalid goals')
        k=(r['league'],d,r['home'],r['away'])
        if k in seen: raise ValueError(f'duplicate result {k}')
        seen.add(k); out.append(dict(date=d,league=r['league'],home=r['home'],away=r['away'],hg=h,ag=a,source=r.get('source',''),season=r.get('season','')))
    return sorted(out,key=lambda x:x['date'])
def subset(rows,team,side,cutoff,league):
    return [r for r in rows if r['date']<cutoff and r['league']==league and r[side]==team]
def mean_goals(rows,side):
    if not rows:return None
    return (sum(r['hg'] if side=='home' else r['ag'] for r in rows)/len(rows),sum(r['ag'] if side=='home' else r['hg'] for r in rows)/len(rows))
def weighted_form(rows,team,side,cutoff,league,season_start,previous_start):
    arr=subset(rows,team,side,cutoff,league)
    season=[r for r in rows if r['league']==league and r['date']<cutoff and r['date']>=season_start and (r['home']==team or r['away']==team)]
    prev=[r for r in arr if previous_start<=r['date']<season_start]
    chunks=[arr[-5:],arr[-10:],season,prev]
    if any(not c for c in chunks):return None,{'counts':list(map(len,chunks)),'reason':'missing sample'}
    rates=[]
    for j,c in enumerate(chunks):
        if j==2:
            rates.append((sum(r['hg'] if r['home']==team else r['ag'] for r in c)/len(c),sum(r['ag'] if r['home']==team else r['hg'] for r in c)/len(c)))
        else:rates.append(mean_goals(c,side))
    result=tuple(sum(W[j]*rates[j][i] for j in range(4)) for i in (0,1))
    return result,{'counts':list(map(len,chunks)),'rates':rates,'weights':W,'result':result,'match_dates':[[str(r['date']) for r in c] for c in chunks]}
def poisson(k,lam):return math.exp(-lam)*lam**k/math.factorial(k)
def distribution(lh,la):
    # Reject invalid parameters before computing any market percentages.
    # This function is a statistical baseline, never calibrated EX FINAL evidence.
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or v>5 for v in (lh,la)):
        raise ValueError('goal intensities must be finite numbers in [0,5]')
    # analytic total goals: sum of independent Poissons
    t=lh+la; over=1-math.exp(-t)*(1+t+t*t/2)
    btts=(1-math.exp(-lh))*(1-math.exp(-la))
    scores=sorted(((f'{h}-{a}',poisson(h,lh)*poisson(a,la)) for h in range(12) for a in range(12)),key=lambda x:-x[1])[:8]
    grid=[(h,a,poisson(h,lh)*poisson(a,la)) for h in range(30) for a in range(30)]
    home_win=sum(p for h,a,p in grid if h>a)
    away_win=sum(p for h,a,p in grid if h<a)
    draw=sum(p for h,a,p in grid if h==a)
    return {'over25':over,'btts':btts,'home_win':home_win,
            'draw':draw,'away_win':away_win,
            'probability_mass':sum(p for h,a,p in grid),
            'top_scores':scores,'lambda_home':lh,'lambda_away':la,'p_11':poisson(1,lh)*poisson(1,la),'p_20':poisson(2,lh)*poisson(0,la),'p_30':poisson(3,lh)*poisson(0,la)}
def calculate(rows,fixture,threshold=.70):
    league=fixture['league']; cutoff=date(fixture['date'])
    ss, ps = season_bounds(league, cutoff)
    if fixture.get('season_start') or fixture.get('previous_start'):
        ss, ps = date(fixture['season_start']), date(fixture['previous_start'])
    if not ps<ss<=cutoff:raise ValueError('season bounds inconsistent')
    home,ha=weighted_form(rows,fixture['home'],'home',cutoff,league,ss,ps)
    away,aa=weighted_form(rows,fixture['away'],'away',cutoff,league,ss,ps)
    base={'fixture':fixture,'samples':{'home':ha,'away':aa},'status':'INCOMPLETE','decision':'NO_FINAL'}
    if home is None or away is None:base['missing']=['historical_home_away_samples'];return base
    # transparent independent baseline; NOT the user's undefined 50/30/20 EX-G model
    lh=max(.05,min(5,(home[0]+away[1])/2));la=max(.05,min(5,(away[0]+home[1])/2))
    d=distribution(lh,la);base['baseline']=d
    base['baseline_over25_pct']=round(100*d['over25'],2)
    base['market_baselines_pct']={
        '2.5_UST':round(100*d['over25'],2),
        'KG_VAR':round(100*d['btts'],2),
        'MS1':round(100*d['home_win'],2),
        'MSX':round(100*d['draw'],2),
        'MS2':round(100*d['away_win'],2),
    }
    base['status']='BASELINE_ONLY';base['missing']=['team_strength_50_30_20_operational_formula','verified_match_conditions','verified_external_factors','ex_g_calibration','odds_snapshot','independent_tur2_sources']
    return base
def audit(rows,fixtures):
    out=[]
    history=HistoricalFeatures(rows)
    for f in fixtures:
        try: r=calculate(rows,f)
        except Exception as e:r={'fixture':f,'status':'ERROR','decision':'NO_FINAL','error':str(e)}
        # deterministic second pass with equality, not independent data-source validation
        try:
            r2=calculate(rows,f)
            r['recompute_consistent']=r==r2
        except Exception:r['recompute_consistent']=False
        if r['status']=='BASELINE_ONLY' and r['recompute_consistent']:
            r['historical_features']=history.fixture(f['league'],f['league'],f['home'],f['away'],date(f['date']))
        out.append(r)
    return out
def baseline_backtest_observations(rows, min_train=30):
    """Yield retrospective predictions from fixtures strictly earlier by date."""
    for r in rows:
        ss, ps = season_bounds(r['league'], r['date'])
        f={'date':str(r['date']),'league':r['league'],'home':r['home'],'away':r['away'],'season_start':str(ss),'previous_start':str(ps)}
        if sum(z['league']==r['league'] and z['date']<r['date'] for z in rows)<min_train:continue
        p=calculate(rows,f)
        if p['status']=='BASELINE_ONLY':
            yield r,p['baseline']


def backtest(rows,min_train=30):
    # strict chronological prediction: prior results only, no random leakage
    preds=[]
    markets = {
        '2.5_UST': ('over25', lambda h, a: h+a>=3),
        'KG_VAR': ('btts', lambda h, a: h>0 and a>0),
        'MS1': ('home_win', lambda h, a: h>a),
        'MS2': ('away_win', lambda h, a: a>h),
    }
    market_predictions = {market: [] for market in markets}
    for r, baseline in baseline_backtest_observations(rows, min_train):
        for market, (metric, settled) in markets.items():
            market_predictions[market].append(
                (r['date'], baseline[metric], int(settled(r['hg'], r['ag'])))
            )
        preds.append(market_predictions['2.5_UST'][-1])
    if not preds:return {'n':0,'status':'INSUFFICIENT_DATA'}
    n=len(preds);brier=sum((p-y)**2 for _,p,y in preds)/n
    bins=[]
    for lo in (0,.1,.2,.3,.4,.5,.6,.7,.8,.9):
        sample=[(p,y) for _,p,y in preds if lo<=p<lo+.1 or (lo==.9 and p==1)]
        if sample:bins.append({'range':f'{lo:.1f}-{lo+.1:.1f}','n':len(sample),'predicted':round(statistics.mean(p for p,y in sample),3),'observed':round(statistics.mean(y for p,y in sample),3)})
    market_audit = {
        market: {
            'n': len(values),
            'brier': round(statistics.mean((p-y)**2 for _,p,y in values), 5),
            'mean_prediction': round(statistics.mean(p for _,p,_ in values), 5),
            'observed_frequency': round(statistics.mean(y for _,_,y in values), 5),
            'chronological_calibration': chronological_intercept(values),
        }
        for market, values in market_predictions.items()
    }
    return {'markets':market_audit,'calibrated':False,'ex_final_allowed':False,'n':n,'brier':round(brier,5),'accuracy_at_70':round(sum(y for _,p,y in preds if p>=.7)/max(1,sum(p>=.7 for _,p,y in preds)),4),'n_at_70':sum(p>=.7 for _,p,y in preds),'calibration_bins':bins,'status':'BASELINE_BACKTEST_ONLY'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',required=True);ap.add_argument('--fixtures');ap.add_argument('--output',default='report.json');ap.add_argument('--backtest',action='store_true');args=ap.parse_args()
    rows=load(args.results);report={'version':'EX v4.3 research engine 0.2','results_rows':len(rows),'source_sha256':hashlib.sha256(Path(args.results).read_bytes()).hexdigest(),'disclaimer':'No EX FINAL without independently specified EX-G formula, verified conditions, odds and source validation.'}
    if args.fixtures:
        with open(args.fixtures,encoding='utf-8-sig',newline='') as f:fixtures=list(csv.DictReader(f))
        report['matches']=audit(rows,fixtures);report['status']='NO_EX_FINAL'
    if args.backtest:report['backtest']=backtest(rows)
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print('Report:',args.output,'; rows:',len(rows),'; EX FINAL: NOT AUTHORIZED')
if __name__=='__main__':main()
