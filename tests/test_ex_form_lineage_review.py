import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from run_ex_form_lineage_review import review


class FormLineageReviewTests(unittest.TestCase):
    def test_publisher_credit_and_distinct_bytes_do_not_certify_origin(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = b"official publication"
            digest = hashlib.sha256(raw).hexdigest()
            (root / digest[:2]).mkdir()
            (root / digest[:2] / digest).write_bytes(raw)
            (root / "espn-1.json").write_text(json.dumps(
                {"header": {"league": {"slug": "ger.1"}, "dataProvider": "Example"}}))
            fixture = {"event_id": "1", "league": "de.1", "kickoff_at": "2026-11-20T20:00:00Z",
                       "team_ids": {"home": "1", "away": "2"}, "score": [1, 0],
                       "official_source": {"sha256": digest, "size": len(raw)},
                       "official_sealed_at": "2026-11-21T00:00:00Z", "provider_sha256": "a" * 64}
            row = {"historical_fixture": fixture, "primary_archive_seal": "2026-11-21T01:00:00Z",
                   "target": "11", "side": "home", "decision_cutoff": "2026-11-22T00:00:00Z",
                   "reproduced_form_windows": ["venue_last5"]}
            with patch("run_ex_form_lineage_review.match_detail"), patch(
                    "run_ex_form_lineage_review.settled_facts", return_value={"score": (1, 0)}):
                report = review({"form_window_date_candidates": [row, {**row, "target": "12"}]},
                                root, root, {"de.1": []})
                self.assertEqual(1, len(report["events"]))
                self.assertEqual(2, len(report["form_uses"]))
                self.assertEqual({"header.dataProvider": "Example"},
                                 report["events"][0]["primary_recheck"]["attribution_fields"])
                self.assertFalse(report["production_allowed"])
                self.assertEqual("BLOCKED_SOURCE_LINEAGE_UNPROVEN", report["form_uses"][1]["status"])
                with self.assertRaisesRegex(ValueError, "lacks pre-cutoff"):
                    review({"form_window_date_candidates": [{**row, "decision_cutoff":
                           fixture["official_sealed_at"]}]}, root, root, {"de.1": []})
