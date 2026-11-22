"""EX v4.3 deterministic Tur-2 and Auto-Control.

Recomputation checks arithmetic reproducibility; it is NOT a second data source.
"""
import hashlib
import json
import math

MARKET_KEYS=("2.5_UST","KG_VAR","MS1","MSX","MS2")

def snapshot(data):
    raw=json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(",",":"),default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def auto_control(match, ingestion=None):
    issues=[]
    if not isinstance(match,dict):
        return {"status":"BLOCKED","issues":["match:invalid"],"ex_final_allowed":False}
    if match.get("recompute_consistent") is not True:
        issues.append("tur2:recompute_mismatch")
    if match.get("status")!="BASELINE_ONLY":
        issues.append("historical_samples:incomplete")
    for gate in ("fixture_lock","odds_lock"):
        if not isinstance(match.get(gate),dict) or match[gate].get("status")!="VERIFIED_INPUT":
            issues.append(gate+":blocked")
    market=match.get("market_baselines_pct")
    if not isinstance(market,dict) or any(k not in market for k in MARKET_KEYS):
        issues.append("market_baselines:missing")
    else:
        values=[market[k] for k in MARKET_KEYS]
        if any(not isinstance(v,(float,int)) or isinstance(v,bool) or not math.isfinite(v)
               or v<0 or v>100 for v in values):
            issues.append("market_baselines:invalid")
        elif abs(sum(market[k] for k in ("MS1","MSX","MS2"))-100)>0.1:
            issues.append("match_result_probabilities:sum_mismatch")
    if not isinstance(ingestion,dict) or ingestion.get("status") not in ("INGESTED", "INGESTED_CROSS_VERIFIED"):
        issues.append("ingestion:blocked")
    if (not isinstance(ingestion,dict) or
            isinstance(ingestion.get("independent_sources_confirmed"),bool) or
            not isinstance(ingestion.get("independent_sources_confirmed"),int) or
            ingestion.get("independent_sources_confirmed",0)<2):
        issues.append("second_source:unverified")
    # Explicitly unimplemented inputs cannot be silently treated as verified.
    issues.extend(["exg:uncalibrated","context:unverified","pup:unverified"])
    return {"status":"BLOCKED" if issues else "CHECKS_PASSED",
            "issues":issues,"snapshot_sha256":snapshot(match),
            "ex_final_allowed":False}
