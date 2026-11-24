"""Synchronize review export digests only; reject changes to fixture identity or scores."""
import json
import re
from pathlib import Path
from ex_strict_review_export_audit import audit_review_exports


def synchronize(source, batches):
    for batch in batches:
        for row in batch["fixtures"]:
            index = row["index"]
            if type(index) is not int or not 0 <= index < len(source["verified"]):
                raise ValueError("Invalid fixture index")
            digest = source["verified"][index]["secondary_sha256"]
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("Invalid source digest")
            row["secondary_sha256"] = digest
    result = audit_review_exports(source, batches)
    if (result["status"] != "EXPORT_INTEGRITY_PASSED_NOT_SOURCE_VERIFIED"
            or result["exported_unique"] != 1177
            or result["league_counts"] != {"en.1": 307, "es.1": 442, "it.1": 428}):
        raise ValueError("Review export integrity failure: " + str(result["issues"]))
    return batches


def main():
    root = Path("reports")
    source = json.loads((root / "latest_multileague_strict_score_reconcile.json").read_text(encoding="utf-8"))
    paths = [root / ("strict_score_review_batch_%02d.json" % i) for i in range(1, 13)]
    batches = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    synchronize(source, batches)
    for path, batch in zip(paths, batches):
        path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
