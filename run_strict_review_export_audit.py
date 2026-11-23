"""Run strict review export integrity audit against the checked-in real reports."""
import json
from pathlib import Path

from ex_strict_review_export_audit import audit_review_exports

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"


def main():
    source = json.loads((REPORTS / "latest_multileague_strict_score_reconcile.json").read_text(encoding="utf-8"))
    batches = [
        json.loads((REPORTS / ("strict_score_review_batch_%02d.json" % i)).read_text(encoding="utf-8"))
        for i in range(1, 13)
    ]
    result = audit_review_exports(source, batches)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result["status"] != "EXPORT_INTEGRITY_PASSED_NOT_SOURCE_VERIFIED":
        raise SystemExit(1)
    if result["exported_unique"] != 1177:
        raise SystemExit("Unexpected record count")
    if result["league_counts"] != {"en.1": 307, "es.1": 442, "it.1": 428}:
        raise SystemExit("Unexpected league distribution")
    if result["independent_score_verified"] or result["ex_final_allowed"]:
        raise SystemExit("Unsafe source verification promotion")


if __name__ == "__main__":
    main()
