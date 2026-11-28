import datetime as dt
import unittest

from run_ex_archive_dispatch import REF, missing_artifacts, recovery_commands


class ArchiveRecoveryTests(unittest.TestCase):
    def test_recovery_uses_only_known_dispatch_outputs_absent_from_archive(self):
        def request(path, *, pages=False):
            if "/contents/" in path:
                return [{"name": "prematch-and-research", "sha": "index", "type": "dir"}]
            if "/git/trees/" in path:
                return {"tree": [{"path": "1.json", "type": "blob"}]}
            if "/workflows/" in path:
                return [{"workflow_runs": [
                    {"id": 20, "head_branch": REF, "event": "workflow_dispatch"},
                    {"id": 21, "head_branch": REF, "event": "pull_request"},
                ]}] if "prospective" in path else [{"workflow_runs": []}]
            self.assertIn("/runs/20/", path)
            return [{"artifacts": [
                {"id": i, "name": name, "expired": status, "digest": "sha256:123"}
                for i, name, status in [(1, "ex-prospective-forecasts", False),
                                         (2, "ex-prospective-forecasts", False),
                                         (3, "ex-prospective-settlement", True),
                                         (4, "unrelated", False)]
            ]}]

        self.assertEqual(([2], [3]), missing_artifacts(dt.date(2026, 11, 25), request))
        operations = recovery_commands(dt.date(2026, 11, 25), list(range(1, 7)))
        self.assertEqual(["artifact_ids=1,2,3,4", "artifact_ids=5,6"], [row[-1] for row in operations])
