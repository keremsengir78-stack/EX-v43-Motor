import json
import unittest
from pathlib import Path
from ex_official_evidence import validate_evidence


class OfficialEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(Path("evidence/official_unresolved_2026_11.json").read_text())

    def test_three_official_records_are_not_merged(self):
        result = validate_evidence(self.document)
        self.assertEqual(result["records"], 3)
        self.assertFalse(result["ex_final_allowed"])

    def test_rejects_final_unlock(self):
        self.document["ex_final_allowed"] = True
        with self.assertRaises(ValueError):
            validate_evidence(self.document)

    def test_rejects_unapproved_source(self):
        self.document["records"][0]["source_url"] = "https://example.com/fixture"
        with self.assertRaises(ValueError):
            validate_evidence(self.document)

    def test_rejects_duplicate(self):
        self.document["records"].append(dict(self.document["records"][0]))
        with self.assertRaises(ValueError):
            validate_evidence(self.document)

    def test_rejects_future_score(self):
        self.document["records"][0]["date"] = "2026-11-23"
        with self.assertRaises(ValueError):
            validate_evidence(self.document)


if __name__ == "__main__":
    unittest.main()
