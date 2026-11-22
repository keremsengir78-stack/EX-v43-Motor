"""Contract tests for the live bridge CLI's fail-closed exit codes."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

import ex_live_bridge_pilot as pilot


class LiveBridgeExitTests(unittest.TestCase):
    def _execute(self, status):
        with tempfile.TemporaryDirectory() as directory:
            output = str(Path(directory) / "report.json")
            with patch.object(pilot, "run_pilot", return_value={
                "status": status, "issues": [], "matched": 0,
                "unmatched": 0, "ambiguous": 0, "ex_final_allowed": False}):
                with patch.object(sys, "argv", ["pilot", "--out", output]):
                    code = pilot.main()
            report = json.loads(Path(output).read_text())
        return code, report

    def test_full_provisional_match_exit_zero(self):
        code, report = self._execute("PROVISIONAL_MATCH_UNAUDITED")
        self.assertEqual(code, 0)
        self.assertFalse(report["ex_final_allowed"])

    def test_partial_match_exit_nonzero(self):
        self.assertEqual(self._execute("PARTIAL_PROVISIONAL_MATCH")[0], 2)

    def test_conflict_exit_nonzero(self):
        self.assertEqual(self._execute("SCORE_CONFLICT")[0], 2)

    def test_blocked_exit_nonzero(self):
        self.assertEqual(self._execute("BLOCKED")[0], 2)

    def test_unknown_status_exit_nonzero(self):
        self.assertEqual(self._execute("UNKNOWN")[0], 2)


if __name__ == "__main__":
    unittest.main()
