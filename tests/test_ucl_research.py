import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from ex_engine import audit, backtest, date
from ex_ucl_strength import audit_league_margins
from run_ucl_baselines import select_rows, team_index, verified_bytes
from run_ucl_research import capture_uefa, UEFA_SNAPSHOT, uefa_fixtures, verify_historical_scores


class UclResearchTests(unittest.TestCase):
    def test_league_alias_deduplicates_and_cross_checks_scores(self):
        _, aliases = team_index({"it.1": {"Inter": ["Internazionale"]}})
        rows, coverage = select_rows([
            ("openfootball", "it.1", "2026-08-20", "Inter", "Roma", 1, 0),
            ("openfootball", "it.1", "2026-09-20", "Inter", "Napoli", 2, 1),
            ("openfootball", "it.1", "2026-10-20", "Inter", "Como", 3, 0),
            ("ESPN", "it.1", "2026-08-20", "Internazionale", "Roma", 1, 0),
            ("ESPN", "it.1", "2026-09-20", "Internazionale", "Napoli", 3, 1),
            ("ESPN", "it.1", "2026-11-24", "Internazionale", "Napoli", 9, 9),
        ], aliases)
        self.assertEqual(["Inter", "Inter"], [row["home"] for row in rows])
        self.assertEqual([1, 3], [row["hg"] for row in rows])
        self.assertEqual("openfootball", coverage[0]["provider"])
        self.assertEqual(1, coverage[0]["exact_score_agreements"])
        self.assertEqual("napoli", coverage[0]["excluded_score_conflicts"][0]["away"])

    def test_provider_selection_uses_season_boundaries(self):
        _, aliases = team_index({"no.1": {"Viking": ["Viking FK"]}})
        rows, coverage = select_rows([
            ("openfootball", "no.1", "2025-11-29", "Viking", "Molde", 1, 0),
            ("ESPN", "no.1", "2026-01-29", "Viking FK", "Molde", 2, 0),
        ], aliases)
        self.assertEqual(2, len(rows))
        self.assertEqual(
            [(2025, "openfootball"), (2026, "ESPN")],
            [(entry["season_start_year"], entry["provider"]) for entry in coverage],
        )

    def test_ambiguous_alias_and_tampered_snapshot_fail(self):
        with self.assertRaisesRegex(ValueError, "Conflicting club alias"):
            team_index({"it.1": {"Inter": ["Milan"], "Milan": []}})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot"
            path.write_bytes(b"modified")
            with self.assertRaisesRegex(ValueError, "Source hash mismatch"):
                verified_bytes(path, "0" * 64)

    def test_uefa_403_replays_pinned_fixture_and_history_excerpt(self):
        url = json.loads(UEFA_SNAPSHOT.with_suffix(".json").read_text())["url"]
        forbidden = HTTPError(url, 403, "Forbidden", None, None)
        with tempfile.TemporaryDirectory() as folder, patch(
            "run_ucl_research.retry_research_request", side_effect=forbidden
        ):
            raw, meta = capture_uefa(Path(folder), url)
            self.assertEqual("archived_excerpt", meta["mode"])
            self.assertEqual(403, meta["live_http_status"])
            self.assertEqual(18, len(uefa_fixtures(raw, 5)))
            self.assertEqual(72, verify_historical_scores(raw, [], {}, 5)["uefa_rows"])
            with self.assertRaisesRegex(ValueError, "URL or SHA-256 mismatch"):
                capture_uefa(Path(folder), url + "?unrecognized")

    def test_uefa_team_page_rejects_duplicate_match_with_conflicting_score(self):
        prefix = b"fixtures-and-results-by-team/<pk-accordion-item>"
        match = (b'08/09/2026 <a href="https://www.uefa.com/uefachampionsleague/'
                 b'match/1--inter-roma">Inter 2-1 Roma</a>')
        raw = prefix + match + b" " + match.replace(b"2-1", b"1-1")
        with self.assertRaisesRegex(ValueError, "Conflicting UEFA team listings"):
            verify_historical_scores(raw, [], {}, 2)

    def test_league_strength_requires_out_of_sample_lift(self):
        train = [("a", "b", 2), ("b", "a", -2)] * 18
        supported = audit_league_margins(train, train[:12])
        self.assertEqual("OBSERVED_LEAGUE_MARGIN_HOLDOUT_IMPROVED", supported["status"])
        self.assertLess(supported["model_mse"], supported["null_mse"])
        self.assertFalse(supported["ex_final_allowed"])
        reversed_scores = [(home, away, -margin) for home, away, margin in train[:12]]
        unsupported = audit_league_margins(train, reversed_scores)
        self.assertEqual("BLOCKED_NO_HOLDOUT_IMPROVEMENT", unsupported["status"])
        self.assertNotIn("league_margins", unsupported)

    def test_tur2_detects_non_over25_drift_and_backtest_covers_four_markets(self):
        baseline = {"status": "BASELINE_ONLY", "baseline_over25_pct": 50, "baseline": {
            "over25": .5, "btts": .4, "home_win": .5, "away_win": .25,
        }}
        drift = {**baseline, "baseline": {**baseline["baseline"], "btts": .7}}
        with patch("ex_engine.calculate", side_effect=[baseline, drift]):
            self.assertFalse(audit([], [{}])[0]["recompute_consistent"])
        rows = [
            {"date": date(day), "league": "en.1", "home": "A", "away": "B", "hg": 1, "ag": 0}
            for day in ("2026-08-01", "2026-08-02")
        ]
        with patch("ex_engine.calculate", return_value=baseline):
            result = backtest(rows, min_train=1)
        self.assertEqual({"2.5_UST", "KG_VAR", "MS1", "MS2"}, set(result["markets"]))
        self.assertEqual(1, result["markets"]["MS1"]["observed_frequency"])
        self.assertEqual(.16, result["markets"]["KG_VAR"]["brier"])
        self.assertFalse(result["calibrated"])

    def test_uefa_clock_and_historical_score_are_checked(self):
        raw = (
            "Kick-offs are 21:00 unless stated; all times CET."
            '<h2>Matchday 1</h2><b>Tuesday 8 September 2026</b>'
            '<a href="/uefachampionsleague/match/1">Inter 2-1 Roma</a>'
            '<h2>Matchday 2</h2><b>Tuesday 24 November 2026</b>'
            '<a href="/uefachampionsleague/match/2">Roma vs Inter</a> (18:45)'
        ).encode()
        self.assertEqual(
            [(datetime(2026, 11, 24, 17, 45, tzinfo=timezone.utc), "roma", "inter")],
            uefa_fixtures(raw, 2),
        )
        espn = [{"date": "2026-09-08", "home": "Internazionale", "away": "Roma",
                 "home_goals": 1, "away_goals": 2}]
        report = verify_historical_scores(raw, espn, {"internazionale": "inter", "roma": "roma"}, 2)
        self.assertEqual(0, report["exact_score_agreements"])
        self.assertEqual(1, len(report["score_conflicts"]))
        self.assertEqual([], report["missing_in_espn"])


if __name__ == "__main__":
    unittest.main()
