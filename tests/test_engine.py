import unittest
import math

from ex_engine import load, audit, backtest
from ex_live_data import run, read_openfootball
from ex_cross_verify import verify, secondary_rows


class TestEXMotor(unittest.TestCase):

    def test_modules_available(self):
        self.assertTrue(callable(load))
        self.assertTrue(callable(audit))
        self.assertTrue(callable(backtest))
        self.assertTrue(callable(run))

    def test_probability_bounds(self):
        for value in (0.0, 0.25, 0.5, 0.75, 1.0):
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 1)

    def test_poisson_normalization(self):
        lam = 2.0
        total = sum(
            math.exp(-lam) * lam**k / math.factorial(k)
            for k in range(30)
        )
        self.assertAlmostEqual(total, 1.0, places=8)

    def test_openfootball_score_variants(self):
        import json
        blob = json.dumps({"matches": [
            {"date": "2026-09-01", "team1": "A", "team2": "B", "score": [2, 1]},
            {"date": "2026-09-02", "team1": "C", "team2": "D", "score": {"ft": [0, 0]}},
            {"date": "2026-09-03", "team1": "E", "team2": "F", "score": None},
        ]}).encode()
        rows, errors, fixtures = read_openfootball(blob, "en.1", "2026-27", {})
        self.assertEqual((len(rows), len(errors), fixtures), (2, 0, 1))

    def test_historical_archive_not_stale(self):
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for season, day in [("2025-26", "2026-05-24"), ("2026-27", "2026-11-19")]:
                p = root / "mirror" / season / "en.1.json"
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps({"matches": [
                    {"date": day, "team1": "A", "team2": "B", "score": [1, 0]}
                ]}))
            report = run(["2025-26", "2026-27"], ["en.1"],
                         root / "out", "2026-11-21", offline=root / "mirror")
            self.assertFalse(report["sources"][0]["stale"])
            self.assertFalse(report["sources"][1]["stale"])
            self.assertEqual(report["status"], "INGESTED_SINGLE_PROVIDER_NOT_CROSS_VERIFIED")
            self.assertFalse(report["ex_final_allowed"])

    def test_stale_active_season_blocks(self):
        import json, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p = root / "mirror" / "2026-27" / "en.1.json"
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({"matches": [
                {"date": "2026-09-20", "team1": "A", "team2": "B", "score": [1, 0]}
            ]}))
            report = run(["2026-27"], ["en.1"], root / "out",
                         "2026-11-21", offline=root / "mirror")
            self.assertEqual(report["status"], "BLOCKED")
            self.assertEqual(report["blocking_sources"][0]["reason"], "stale")

    def test_independent_source_match_and_conflict(self):
        primary=[{"date":"2026-11-18","league":"en.1","home":"Arsenal",
                  "away":"Chelsea","home_goals":2,"away_goals":1}]
        other=[dict(primary[0])]
        ok=verify(primary,other,"2026-11-21")
        self.assertEqual(ok["matched"],1)
        self.assertEqual(ok["conflicts"],[])
        other[0]["away_goals"]=2
        bad=verify(primary,other,"2026-11-21")
        self.assertEqual(len(bad["conflicts"]),1)

    def test_independent_source_offline_csv(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"2627_E0.csv"
            p.write_text("Date,HomeTeam,AwayTeam,FTHG,FTAG\\n18/11/2026,Arsenal,Chelsea,2,1\\n")
            rows,meta=secondary_rows("2026-27","en.1",temp)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["home_goals"],2)
            self.assertEqual(meta["provider"],"football-data.co.uk")


if __name__ == "__main__":
    unittest.main()
