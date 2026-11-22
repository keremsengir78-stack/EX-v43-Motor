import json
import unittest
from pathlib import Path
from ex_official_reconcile import reconcile_official_evidence


class OfficialReconcileTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads(Path("evidence/official_unresolved_2026_11.json").read_text())
        records = self.evidence["records"]
        self.audit = {
            "as_of": self.evidence["as_of"],
            "technical_gate": "PASSED_AUDIT_COMPARISON",
            "review_queue_complete": True,
            "reviewed_matched": 18,
            "reviewed_unmatched": 3,
            "ex_final_allowed": False,
            "review_queue": [{"fixtures": [
                {k: row[k] for k in ("league", "date", "home", "away")}
                for row in records]}],
        }

    def test_all_three_evidence_records_attach_without_certification(self):
        result = reconcile_official_evidence(self.audit, self.evidence)
        self.assertEqual(result["official_evidence_attached"], 3)
        self.assertEqual(result["official_evidence_missing"], 0)
        self.assertEqual(result["reviewed_matched"], 18)
        self.assertEqual(result["reviewed_unmatched"], 3)
        self.assertFalse(result["ex_final_allowed"])
        self.assertFalse(result["independent_sources_confirmed"])

    def test_rejects_wrong_opponent(self):
        self.evidence["records"][0]["away"] = "Wrong opponent"
        with self.assertRaises(ValueError):
            reconcile_official_evidence(self.audit, self.evidence)

    def test_rejects_different_cutoff(self):
        self.audit["as_of"] = "2026-11-21"
        with self.assertRaises(ValueError):
            reconcile_official_evidence(self.audit, self.evidence)

    def test_rejects_incomplete_review_queue(self):
        self.audit["review_queue_complete"] = False
        with self.assertRaises(ValueError):
            reconcile_official_evidence(self.audit, self.evidence)

    def test_rejects_audit_final_unlock(self):
        self.audit["ex_final_allowed"] = True
        with self.assertRaises(ValueError):
            reconcile_official_evidence(self.audit, self.evidence)


if __name__ == "__main__":
    unittest.main()
