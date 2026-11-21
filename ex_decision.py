"""EX-G evidence-weighted decision layer. Explicitly supplied, audited inputs only.

This is a reproducible weighting mechanism, NOT a calibrated probability model.
A percentage must not be labelled EX FINAL without external calibration.
"""
import math
import datetime as dt

WEIGHTS={"team_strength":0.50,"match_conditions":0.30,"external_factors":0.20}
MARKETS=("2.5_UST","KG_VAR","MS1","MS2")

def weighted_evidence(features, as_of=None):
    """Each feature: {'score': float [0,1], 'verified': bool, 'source': str,
    'timestamp': ISO 8601}. Missing evidence blocks instead of being imputed."""
    issues=[];contributions={}
    cutoff=None
    if as_of:
        if isinstance(as_of,str) and len(as_of)==10:
            cutoff=dt.datetime.combine(dt.date.fromisoformat(as_of),dt.time.min,dt.timezone.utc)
        else:
            cutoff=dt.datetime.fromisoformat(as_of.replace('Z','+00:00'))
            if cutoff.tzinfo is None:
                raise ValueError('as_of must be timezone-aware')
    # The cutoff is exclusive: a YYYY-MM-DD run cannot use evidence
    # from any time on that date or later.
    for key,weight in WEIGHTS.items():
        item=features.get(key)
        if not isinstance(item,dict):
            issues.append(key+":missing");continue
        score=item.get("score")
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not math.isfinite(score) or not 0<=score<=1:
            issues.append(key+":invalid_score");continue
        if item.get("verified") is not True or not item.get("source") or not item.get("timestamp"):
            issues.append(key+":unverified");continue
        try:
            timestamp=dt.datetime.fromisoformat(item["timestamp"].replace("Z","+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("timezone missing")
            if cutoff is not None and timestamp>=cutoff:
                issues.append(key+":future_evidence");continue
        except (ValueError,TypeError,AttributeError):
            issues.append(key+":invalid_timestamp");continue
        contributions[key]=round(weight*score,8)
    return {"status":"EVIDENCE_COMPLETE_UNCALIBRATED" if not issues else "BLOCKED",
            "weighted_score":round(sum(contributions.values()),8) if not issues else None,
            "contributions":contributions,"issues":issues,
            "weights":WEIGHTS,"calibrated_probability":None,"ex_final_allowed":False}

def assess_markets(evidence_by_market, as_of=None):
    result={m:weighted_evidence(evidence_by_market.get(m,{}),as_of=as_of) for m in MARKETS}
    return {"markets":result,"evidence_complete":all(v["status"]=="EVIDENCE_COMPLETE_UNCALIBRATED" for v in result.values()),
            "pup_allowed":False,"ex_final_allowed":False,
            "reason":"PUP requires independently calibrated market probabilities; evidence weights alone are not probabilities"}
