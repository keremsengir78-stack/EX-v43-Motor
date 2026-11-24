"""EX-G evidence-weighted decision layer. Explicitly supplied, audited inputs only.

This is a reproducible weighting mechanism, NOT a calibrated probability model.
A percentage must not be labelled EX FINAL without external calibration.
"""
import math
import datetime as dt
import re
from ex_fixture_odds import check_odds

WEIGHTS={"team_strength":0.50,"match_conditions":0.30,"external_factors":0.20}
MARKETS=("2.5_UST","KG_VAR","MS1","MS2")
# Approved mappings operate solely on the weighted, market-specific evidence score.
# Registration requires a reviewed code change. Request data cannot install a mapping.
_APPROVED_CALIBRATORS = {}


def ex_g_from_evidence(market, weighted):
    """Apply an approved market calibration independently of bookmaker inputs."""
    issues = list(weighted["issues"])
    calibrate = _APPROVED_CALIBRATORS.get(market)
    if calibrate is None:
        issues.append("calibration:uncertified")
    probability = None
    if not issues and weighted["status"] == "EVIDENCE_COMPLETE_UNCALIBRATED":
        value = calibrate(weighted["weighted_score"])
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
            issues.append("calibration:invalid_probability")
        else:
            probability = value
    return {
        "status": "EX_G_AVAILABLE" if probability is not None else "BLOCKED",
        "market": market, "probability": probability, "issues": issues,
    }


def assess_market_value(market, ex_g, quote, as_of):
    """Apply the market price gate and compute a probability difference when available."""
    if isinstance(quote, dict) and quote.get("market") != market:
        odds = {"status": "BLOCKED", "issues": ["odds:market_mismatch"],
                "decision": "NO_FINAL", "ex_final_allowed": False}
    else:
        odds = check_odds(quote, as_of)
    implied = 1 / quote["decimal_odds"] if odds["status"] == "VERIFIED_INPUT" else None
    probability = (ex_g["probability"]
                   if ex_g["status"] == "EX_G_AVAILABLE" and ex_g["market"] == market else None)
    if isinstance(probability, bool) or not isinstance(probability, (int, float)) or not 0 <= probability <= 1:
        probability = None
    issues = []
    if probability is None:
        issues.append("certified_ex_g_probability")
    if implied is None:
        issues.append("verified_market_quote")
    return {
        "odds_lock": odds, "bookmaker_implied_probability": implied, "ex_d_required_inputs": issues,
        "ex_d": probability - implied if not issues else None,
    }

def weighted_evidence(features, as_of=None):
    """Each feature: {'score': float [0,1], 'verified': bool, 'source': str,
    'timestamp': ISO 8601}. Missing evidence blocks instead of being imputed."""
    if not isinstance(features,dict):
        features={}
    issues=[];contributions={}
    cutoff=None
    if as_of is not None:
        try:
            if not isinstance(as_of,str) or not as_of.strip():
                raise ValueError("as_of must be a nonempty ISO date or datetime")
            if len(as_of)==10:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}",as_of):
                    raise ValueError("analysis date must be YYYY-MM-DD")
                cutoff=dt.datetime.combine(dt.date.fromisoformat(as_of),dt.time.min,dt.timezone.utc)
            else:
                if not re.match(r"^\d{4}-\d{2}-\d{2}T",as_of):
                    raise ValueError('analysis timestamp must start with YYYY-MM-DDT')
                cutoff=dt.datetime.fromisoformat(as_of.replace('Z','+00:00'))
                if cutoff.tzinfo is None or cutoff.utcoffset() is None:
                    raise ValueError('as_of must be timezone-aware')
        except (ValueError,TypeError,OverflowError):
            # Never accept evidence if the analysis cutoff cannot be established.
            return {"status":"BLOCKED","weighted_score":None,"contributions":{},
                    "issues":["invalid_as_of"],"weights":WEIGHTS,
                    "calibrated_probability":None,"ex_final_allowed":False}
    # The cutoff is exclusive: a YYYY-MM-DD run cannot use evidence
    # from any time on that date or later.
    for key,weight in WEIGHTS.items():
        item=features.get(key)
        if not isinstance(item,dict):
            issues.append(key+":missing");continue
        score=item.get("score")
        if isinstance(score,bool) or not isinstance(score,(int,float)) or not 0<=score<=1 or not math.isfinite(score):
            issues.append(key+":invalid_score");continue
        if (item.get("verified") is not True or not isinstance(item.get("source"),str)
                or not item["source"].strip() or not isinstance(item.get("timestamp"),str)
                or not item["timestamp"].strip()):
            issues.append(key+":unverified");continue
        try:
            if not re.match(r"^\d{4}-\d{2}-\d{2}T",item["timestamp"]):
                raise ValueError("evidence timestamp must be canonical")
            timestamp=dt.datetime.fromisoformat(item["timestamp"].replace("Z","+00:00"))
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
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
    if not isinstance(evidence_by_market,dict):
        evidence_by_market={}
    result={m:weighted_evidence(evidence_by_market.get(m,{}),as_of=as_of) for m in MARKETS}
    for market, record in result.items():
        record["ex_g"] = ex_g_from_evidence(market, record)
        record["calibrated_probability"] = record["ex_g"]["probability"]
    return {"markets":result,"evidence_complete":all(v["status"]=="EVIDENCE_COMPLETE_UNCALIBRATED" for v in result.values()),
            "pup_allowed":False,"ex_final_allowed":False,
            "reason":"PUP requires independently calibrated market probabilities; evidence weights alone are not probabilities"}
