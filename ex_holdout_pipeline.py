"""Reproducible chronological audit from frozen pre-match predictions and settled fixtures.

No probability fitting, no automatic source verification and no EX FINAL promotion.
"""
from ex_calibration_join import join_calibration_records
from ex_out_of_sample_audit import audit_out_of_sample
from ex_calibration_audit import MARKETS
from ex_temporal_validation import _timestamp


def audit_joined_holdout(predictions, fixtures, market, evaluation_start, cutoff,
                         min_train=30, min_test=30):
    blocked = lambda issues, join=None, holdout=None: {
        "status": "BLOCKED", "issues": issues, "join": join,
        "holdout": holdout, "calibration_certified": False,
        "pup_allowed": False, "ex_final_allowed": False}
    if not isinstance(market, str) or market not in MARKETS:
        return blocked(["market:unsupported"])
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 30
           for x in (min_train, min_test)):
        return blocked(["sample_threshold:invalid"])
    try:
        if _timestamp(evaluation_start) >= _timestamp(cutoff):
            return blocked(["evaluation_window:invalid"])
    except (ValueError, TypeError, OverflowError):
        return blocked(["evaluation_window:invalid"])
    # A holdout audit requires independently timestamped result records.
    # Legacy joins may omit settlement provenance, but holdout certification cannot.
    if not isinstance(fixtures, list) or not fixtures:
        return blocked(["fixtures:missing"])
    if any(not isinstance(row, dict) or not isinstance(row.get("settled_at"), str)
           or not row["settled_at"].strip() for row in fixtures):
        return blocked(["fixtures:settlement_provenance_missing"])
    if not isinstance(predictions, list) or not predictions:
        return blocked(["predictions:missing"])
    if any(not isinstance(row, dict) or not isinstance(row.get("source"), str)
           or not row["source"].strip() for row in predictions):
        return blocked(["predictions:source_missing"])
    joined = join_calibration_records(predictions, fixtures, market, cutoff,
                                      min_samples=min_train + min_test)
    if joined["status"] != "AUDIT_COMPLETE_NOT_CALIBRATED":
        return blocked(["join:" + x for x in joined["issues"]], join=joined)
    holdout = audit_out_of_sample(joined["joined_records"], market,
                                  evaluation_start, cutoff,
                                  min_train=min_train, min_test=min_test)
    if holdout["status"] != "OUT_OF_SAMPLE_AUDIT_COMPLETE_NOT_CERTIFIED":
        return blocked(["holdout:" + x for x in holdout["issues"]],
                       join=joined, holdout=holdout)
    return {"status": "HOLDOUT_AUDITED_NOT_CERTIFIED", "issues": [],
            "join": joined, "holdout": holdout,
            "calibration_certified": False, "pup_allowed": False,
            "ex_final_allowed": False}
