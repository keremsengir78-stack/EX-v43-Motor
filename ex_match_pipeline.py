"""End-to-end verified-record evidence processing for one EX v4.3 market.

Accepts already collected fixture records and explicitly audited EX-G inputs.
This is not an online data fetcher and never promotes evidence to EX FINAL.
"""
from ex_window_builder import build_windows
from ex_evidence_pipeline import prepare_market_evidence


def process_match_evidence(market, records, venue, season, previous_season,
                           feature_scores, as_of):
    built = build_windows(records, venue, season, previous_season, as_of)
    if built["status"] != "WINDOWS_READY":
        return {"status": "BLOCKED", "issues": ["window:" + x for x in built["issues"]],
                "windows": built, "evidence": None, "calibrated_probability": None,
                "pup_allowed": False, "ex_final_allowed": False}
    evidence = prepare_market_evidence(market, built["windows"], feature_scores, as_of)
    return {"status": "EVIDENCE_READY_UNCALIBRATED"
            if evidence["status"] == "EVIDENCE_READY_UNCALIBRATED" else "BLOCKED",
            "issues": evidence["issues"], "windows": built, "evidence": evidence,
            "calibrated_probability": None, "pup_allowed": False,
            "ex_final_allowed": False}
