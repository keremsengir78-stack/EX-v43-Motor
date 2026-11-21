import unittest
import math

from ex_engine import load, audit, backtest, distribution
from ex_live_data import run, read_openfootball
from ex_cross_verify import verify, secondary_rows, norm
from ex_decision import weighted_evidence, assess_markets
from ex_fixture_odds import check_fixture, check_odds
from ex_auto_control import auto_control, snapshot


class TestEXMotor(unittest.TestCase):

    def test_exg_missing_evidence_blocks(self):
        r=weighted_evidence({"team_strength":{"score":0.8,"verified":True,
                                               "source":"sample","timestamp":"2026-11-21T10:00:00Z"}})
        self.assertEqual(r["status"],"BLOCKED")
        self.assertIsNone(r["weighted_score"])
        self.assertFalse(r["ex_final_allowed"])

    def test_exg_weighted_score_is_not_probability(self):
        f={name:{"score":score,"verified":True,"source":"test",
                 "timestamp":"2026-11-21T10:00:00Z"}
           for name,score in [("team_strength",0.8),("match_conditions",0.6),
                              ("external_factors",0.5)]}
        r=weighted_evidence(f)
        self.assertAlmostEqual(r["weighted_score"],0.68)
        self.assertIsNone(r["calibrated_probability"])
        self.assertFalse(r["ex_final_allowed"])
        self.assertFalse(assess_markets({"KG_VAR":f})["pup_allowed"])

    def test_fixture_and_odds_lock(self):
        fixture={"date":"2026-11-22","league":"en.1","home":"A","away":"B",
                 "fixture_source":"official","fixture_checked_at":"2026-11-21T10:00:00Z"}
        self.assertEqual(check_fixture(fixture,"2026-11-21")["status"],"VERIFIED_INPUT")
        self.assertEqual(check_fixture({},"2026-11-21")["status"],"BLOCKED")
        snap={"decimal_odds":1.19,"market":"KG_VAR","bookmaker":"test",
              "source":"test","observed_at":"2026-11-21T10:00:00Z"}
        self.assertEqual(check_odds(snap,"2026-11-21T11:00:00Z")["decision"],"PASS_ODDS_1_19_OR_LOWER")
        snap["decimal_odds"]=1.20
        self.assertEqual(check_odds(snap,"2026-11-21T11:00:00Z")["decision"],"NO_FINAL")
        self.assertEqual(check_odds(None,"2026-11-21T11:00:00Z")["status"],"BLOCKED")

    def test_auto_control_never_promotes_baseline(self):
        report=auto_control({"status":"BASELINE_ONLY","recompute_consistent":True,
                             "market_baselines_pct":{"2.5_UST":55,"KG_VAR":50,
                                                     "MS1":45,"MSX":25,"MS2":30}},
                            {"status":"INGESTED_SINGLE_PROVIDER_NOT_CROSS_VERIFIED",
                             "independent_sources_confirmed":1})
        self.assertFalse(report["ex_final_allowed"])
        self.assertIn("exg:uncalibrated",report["issues"])
        self.assertEqual(snapshot({"b":2,"a":1}),snapshot({"a":1,"b":2}))

    def test_cross_provider_reviewed_alias(self):
        primary=[{"date":"2026-11-18","league":"en.1","home":"Manchester United",
                  "away":"Wolverhampton Wanderers","home_goals":2,"away_goals":1}]
        secondary=[{"date":"2026-11-18","league":"en.1","home":"Man United",
                    "away":"Wolves","home_goals":2,"away_goals":1}]
        self.assertEqual(verify(primary,secondary,"2026-11-21")["matched"],0)
        mapping={"en.1":{norm("Man United"):"Manchester United",
                         norm("Wolves"):"Wolverhampton Wanderers"}}
        result=verify(primary,secondary,"2026-11-21",mapping)
        self.assertEqual(result["status"],"VERIFIED")
        self.assertEqual(result["matched"],1)

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

    def test_market_probability_consistency(self):
        d=distribution(1.6,1.2)
        self.assertAlmostEqual(d["home_win"]+d["draw"]+d["away_win"],1,places=8)
        self.assertAlmostEqual(d["probability_mass"],1,places=8)
        for name in ("over25","btts","home_win","draw","away_win"):
            self.assertTrue(0 <= d[name] <= 1)

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
            p.write_text("Date,HomeTeam,AwayTeam,FTHG,FTAG\n18/11/2026,Arsenal,Chelsea,2,1\n")
            rows,meta=secondary_rows("2026-27","en.1",temp)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["home_goals"],2)
            self.assertEqual(meta["provider"],"football-data.co.uk")


if __name__ == "__main__":
    unittest.main()
