"""EX v4.3 out-of-sample audit of historical probability records.

Evaluation records are audited only after strict chronological separation.
This is a validation report, not model training or calibration certification.
"""
from ex_temporal_validation import chronological_split
from ex_calibration_audit import audit_predictions, MARKETS


def audit_out_of_sample(records, market, evaluation_start, cutoff,
                        min_train=30, min_test=30):
    if market not in MARKETS:
        return {"status": "BLOCKED", "issues": ["market:unsupported"],
                "split": None, "evaluation": None,
                "calibration_certified": False, "ex_final_allowed": False}
    if not isinstance(records, list):
        records = []
    mismatches = ["record:%d:market_mismatch" % i
                  for i, row in enumerate(records)
                  if not isinstance(row, dict) or row.get("market") != market]
    if mismatches:
        return {"status": "BLOCKED", "issues": mismatches, "split": None,
                "evaluation": None, "calibration_certified": False,
                "ex_final_allowed": False}
    split = chronological_split(records, evaluation_start,
                                min_train=min_train, min_test=min_test)
    if split["status"] != "CHRONOLOGICAL_SPLIT_READY":
        return {"status": "BLOCKED", "issues": ["split:" + x for x in split["issues"]],
                "split": split, "evaluation": None,
                "calibration_certified": False, "ex_final_allowed": False}
    evaluation = audit_predictions(split["test"], market, cutoff,
                                   min_samples=max(30, min_test))
    return {"status": "OUT_OF_SAMPLE_AUDIT_COMPLETE_NOT_CERTIFIED"
            if evaluation["status"] == "AUDIT_COMPLETE_NOT_CALIBRATED" else "BLOCKED",
            "issues": evaluation["issues"], "split": split,
            "evaluation": evaluation, "calibration_certified": False,
            "ex_final_allowed": False}
