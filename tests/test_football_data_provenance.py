import hashlib
import tempfile
import unittest
from pathlib import Path
from ex_cross_verify import secondary_rows, MAX_SECONDARY_BYTES


class FootballDataProvenanceTests(unittest.TestCase):
    def test_offline_csv_has_auditable_sha256(self):
        raw = b"Date,HomeTeam,AwayTeam,FTHG,FTAG\n01/11/2026,Arsenal,Chelsea,2,1\n"
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "2627_E0.csv").write_bytes(raw)
            rows, meta = secondary_rows("2026-2027", "en.1", offline=folder)
        self.assertEqual(meta["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(meta["raw_bytes"], len(raw))
        self.assertEqual(meta["retrieval_mode"], "offline")
        self.assertEqual(meta["rows"], 1)
        self.assertEqual(rows[0]["home_goals"], 2)

    def test_missing_offline_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            rows, meta = secondary_rows("2026-2027", "en.1", offline=folder)
        self.assertEqual(rows, [])
        self.assertIn("error", meta)

    def test_invalid_season_blocks_without_fetch(self):
        for season in ("2026-2028", "../2026-2027", "2026-27", None):
            rows, meta = secondary_rows(season, "en.1")
            self.assertEqual(rows, [])
            self.assertEqual(meta["error"], "invalid season")

    def test_oversized_offline_csv_blocks(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "2627_E0.csv").write_bytes(b"x" * (MAX_SECONDARY_BYTES + 1))
            rows, meta = secondary_rows("2026-2027", "en.1", offline=folder)
        self.assertEqual(rows, [])
        self.assertIn("size limit", meta["error"])

    def test_unsupported_league_blocks(self):
        rows, meta = secondary_rows("2026-2027", "xx.1")
        self.assertEqual(rows, [])
        self.assertIn("error", meta)


if __name__ == "__main__":
    unittest.main()
