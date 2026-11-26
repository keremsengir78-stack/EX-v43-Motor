import unittest
from unittest.mock import Mock

from ex_context_evidence import reviewed_context
from ex_history_archive import utc
from run_ex_historical_evidence import compare_results


class HistoricalEvidenceTests(unittest.TestCase):
    def test_official_results_require_oriented_identity_exact_time_and_new_bytes(self):
        kickoff = "2026-11-25T20:00:00Z"
        teams = {"home": "1", "away": "2"}
        primary = {"event_id": "1", "competition": "eng.1", "teams": teams, "kickoff": utc(kickoff),
                   "finished": utc("2026-11-25T22:00:00Z"), "score": (1, 0), "source_sha256": "a" * 64}
        fixture = {"league": "en.1", "names": {"home": "Home", "away": "Away"}, "teams": teams}
        raw = {"url": "https://www.premierleague.com/results", "retrieved_at": "2026-11-26T10:00:00Z",
               "sha256": "b" * 64}
        row = {"league": "en.1", "date": "2026-11-25", "kickoff_at": kickoff, "home": "Home",
               "away": "Away", "official_score": [1, 0], "raw_evidence": raw}
        self.assertEqual(1, len(compare_results([primary], [fixture], [row, row])[0]))
        for alternate in ({**row, "home": "Away", "away": "Home"},
                          {**row, "kickoff_at": "2026-11-25T20:01:00Z"},
                          {**row, "raw_evidence": {**raw, "sha256": primary["source_sha256"]}}):
            self.assertEqual([], compare_results([primary], [fixture], [alternate])[0])
        conflict = {**row, "official_score": [2, 0]}
        self.assertEqual([], compare_results([primary], [fixture], [row, conflict])[0])

    def test_context_requires_both_teams_and_replays_dated_source_bytes(self):
        fixture = {"event_id": "1", "league": "en.1", "team_ids": {"home": "1", "away": "2"},
                   "kickoff_at": "2026-11-27T20:00:00Z"}
        source = {"retrieved_at": "2026-11-27T16:00:00Z", "url": "https://www.premierleague.com/evidence"}
        entry = {"finding": "Club review", "published_at": "2026-11-27T15:00:00Z", "source": source}
        bundle = {"fixture": fixture, "accepted_at": "2026-11-27T17:00:00Z",
                  "teams": {side: {"team_id": club, "important_absences": entry, "rotation": entry}
                            for side, club in fixture["team_ids"].items()}}
        load = {"completion_observations": [{"kickoff_at": "2026-11-25T20:00:00Z",
                "completion_upper_bound": "2026-11-25T22:00:00Z", "available_at": "2026-11-26T07:00:00Z",
                "source_sha256": "a" * 64}], "rest_hours_since_archived_full_time_capped_at_336": 46}
        workload = {"home": load, "away": load}
        cutoff = utc("2026-11-27T18:00:00Z")
        replay = Mock()
        self.assertEqual("CONTEXT_CROSS_VERIFIED", reviewed_context(bundle, fixture, workload, cutoff, replay)["status"])
        self.assertEqual(4, replay.call_count)
        self.assertIsNone(reviewed_context(bundle, fixture, {"home": load}, cutoff, replay))
        replay.side_effect = OSError()
        self.assertIsNone(reviewed_context(bundle, fixture, workload, cutoff, replay))

    def test_probe_replays_discovery_and_checks_claimed_counts_before_yielding(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        from run_ex_official_queue_join import source_rows

        source = {"url": "https://www.bundesliga.com/results"}
        replayed = (b"raw", utc("2026-11-26T10:00:00Z"))
        with TemporaryDirectory() as tmp, patch("run_ex_official_queue_join.HistoryArchive") as archive, \
                patch("run_ex_official_queue_join.dfl_scores", return_value=([{"date": "2026-11-25"}], [])) as parse:
            root = Path(tmp)
            archive.return_value._load.return_value = replayed
            report = root / "report.json"
            report.write_text(json.dumps({"discovery": {"source": source},
                                          "de.2": {"parsed_completed_rows": 0, "sources": [source],
                                                   "state": "NO_RESULT_PARSER_OR_ROWS"}}))
            self.assertEqual([], list(source_rows(root)))
            self.assertEqual(2, archive.return_value._load.call_count)
            parse.assert_not_called()
            report.write_text(json.dumps({"de.2": {"parsed_completed_rows": 2, "sources": [source]}}))
            with self.assertRaisesRegex(ValueError, "replay count differs"):
                next(source_rows(root))
