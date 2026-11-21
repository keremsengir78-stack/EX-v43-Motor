import unittest
import math

from ex_engine import load, audit, backtest, distribution
from ex_live_data import run, read_openfootball
from ex_cross_verify import verify, secondary_rows, norm, secondary_only_after_cutoff, reconcile_staged_with_third, validate_third_provenance, validate_third_results
from ex_decision import weighted_evidence, assess_markets
from ex_fixture_odds import check_fixture, check_odds
from ex_auto_control import auto_control, snapshot
from ex_espn_provider import parse_espn_scoreboard


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
                 "fixture_source":"official","fixture_checked_at":"2026-11-21T10:00:00Z",
                 "kickoff_at":"2026-11-22T18:00:00+03:00"}
        self.assertEqual(check_fixture(fixture,"2026-11-21")["status"],"VERIFIED_INPUT")
        self.assertEqual(check_fixture({},"2026-11-21")["status"],"BLOCKED")
        snap={"decimal_odds":1.19,"market":"KG_VAR","bookmaker":"test",
              "source":"test","observed_at":"2026-11-21T10:00:00Z"}
        self.assertEqual(check_odds(snap,"2026-11-21T11:00:00Z")["decision"],"PASS_ODDS_1_19_OR_LOWER")
        snap["decimal_odds"]=1.20
        self.assertEqual(check_odds(snap,"2026-11-21T11:00:00Z")["decision"],"NO_FINAL")
        self.assertEqual(check_odds(None,"2026-11-21T11:00:00Z")["status"],"BLOCKED")
        self.assertEqual(check_odds(snap,"2026-11-21T10:00:00Z")["status"],"BLOCKED")
        self.assertIn("odds:not_before_kickoff",check_odds(snap,"2026-11-21T10:00:00Z")["issues"])
        self.assertEqual(check_fixture({**fixture,"kickoff_at":"2026-11-22T18:00:00"},"2026-11-21")["status"],"BLOCKED")
        self.assertEqual(check_fixture({k:v for k,v in fixture.items() if k!="kickoff_at"},"2026-11-21")["status"],"BLOCKED")

    def test_auto_control_never_promotes_baseline(self):
        report=auto_control({"status":"BASELINE_ONLY","recompute_consistent":True,
                             "market_baselines_pct":{"2.5_UST":55,"KG_VAR":50,
                                                     "MS1":45,"MSX":25,"MS2":30}},
                            {"status":"INGESTED_SINGLE_PROVIDER_NOT_CROSS_VERIFIED",
                             "independent_sources_confirmed":1})
        self.assertFalse(report["ex_final_allowed"])
        self.assertIn("exg:uncalibrated",report["issues"])
        self.assertEqual(snapshot({"b":2,"a":1}),snapshot({"a":1,"b":2}))

    def test_integrated_secondary_freshness_block_and_quarantine(self):
        import csv, json, subprocess, sys, tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            primary=root/"primary"/"2026-27"/"en.1.json"
            primary.parent.mkdir(parents=True)
            primary.write_text(json.dumps({"matches":[
                {"date":"2026-11-15","team1":"Arsenal","team2":"Chelsea","score":[1,0]}
            ]}))
            secondary=root/"secondary"
            secondary.mkdir()
            (secondary/"2627_E0.csv").write_text(
                "Date,HomeTeam,AwayTeam,FTHG,FTAG\n"
                "15/11/2026,Arsenal,Chelsea,1,0\n"
                "19/11/2026,Leeds,Everton,2,1\n")
            script=Path(__file__).resolve().parents[1]/"ex_one_command.py"
            subprocess.run([sys.executable,str(script),"--as-of","2026-11-21",
                            "--seasons","2026-27","--leagues","en.1",
                            "--offline",str(root/"primary"),
                            "--secondary-offline",str(secondary),
                            "--outdir",str(root/"out")],
                           check=True,capture_output=True,text=True)
            audit=json.loads((root/"out"/"audit.json").read_text())
            staged=json.loads((root/"out"/"secondary_only_unverified.json").read_text())
            report=json.loads((root/"out"/"full_report.json").read_text())
            self.assertEqual(audit["independent_matches_confirmed"],1)
            self.assertEqual(audit["secondary_newer_unverified_results"],1)
            self.assertEqual(audit["status"],"BLOCKED")
            self.assertIn("secondary_newer_results_not_independently_verified",
                          [x["reason"] for x in audit["blocking_sources"]])
            self.assertEqual(len(staged),1)
            self.assertEqual(staged[0]["home"],"Leeds")
            self.assertEqual(staged[0]["verification_status"],"SECONDARY_ONLY_UNVERIFIED")
            self.assertFalse(report["ex_final_allowed"])

    def test_espn_third_provider_completed_scores_only(self):
        def event(day,completed=True):
            return {"date":day+"T18:00:00Z",
                    "status":{"type":{"completed":completed}},
                    "competitions":[{"competitors":[
                        {"homeAway":"home","team":{"displayName":"Arsenal"},"score":"2"},
                        {"homeAway":"away","team":{"displayName":"Chelsea"},"score":"1"}]}]}
        data={"events":[event("2026-11-19"),event("2026-11-20",False),
                        event("2026-11-21")]}
        rows=parse_espn_scoreboard(data,"en.1","2026-11-21")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["home_goals"],2)
        self.assertEqual(rows[0]["away_goals"],1)
        with self.assertRaises(ValueError):
            parse_espn_scoreboard(data,"tr.1","2026-11-21")
        with self.assertRaises(ValueError):
            parse_espn_scoreboard({"events":None},"en.1","2026-11-21")

    def test_third_source_input_validation(self):
        row={"date":"2026-11-19","league":"en.1","home":"Arsenal",
             "away":"Chelsea","home_goals":1,"away_goals":0}
        self.assertEqual(len(validate_third_results([row],"2026-11-21")),1)
        for invalid in ([row,row],
                        [{**row,"date":"2026-11-21"}],
                        [{**row,"away":"Arsenal"}],
                        [{**row,"home_goals":True}],
                        [{**row,"away_goals":31}],
                        [{**row,"league":""}]):
            with self.assertRaises(ValueError):
                validate_third_results(invalid,"2026-11-21")

    def test_third_source_rejects_duplicate_and_cutoff_leakage(self):
        row={"date":"2026-11-19","league":"en.1","home":"Arsenal",
             "away":"Chelsea","home_goals":1,"away_goals":0}
        duplicate=reconcile_staged_with_third([row,row],[row],"2026-11-21")
        self.assertEqual(duplicate["verified_count"],1)
        self.assertEqual(duplicate["unresolved_count"],1)
        self.assertEqual(duplicate["status"],"PARTIAL")
        self.assertEqual(duplicate["unresolved"][0]["third_source_status"],"DUPLICATE_STAGED_FIXTURE")
        future={**row,"date":"2026-11-21"}
        cutoff=reconcile_staged_with_third([future],[future],"2026-11-21")
        self.assertEqual(cutoff["verified_count"],0)
        self.assertEqual(cutoff["unresolved"][0]["third_source_status"],"AT_OR_AFTER_CUTOFF")
        self.assertFalse(cutoff["ex_final_allowed"])

    def test_third_source_provenance_gate(self):
        for provider in ("OpenFootball","football-data.co.uk",""):
            with self.assertRaises(ValueError):
                validate_third_provenance(provider,"https://example.org/results")
        with self.assertRaises(ValueError):
            validate_third_provenance("Independent Sports","http://example.org/results")
        valid=validate_third_provenance("Independent Sports","https://example.org/results")
        self.assertEqual(valid["provenance_status"],"DECLARED_NOT_INDEPENDENTLY_AUDITED")

    def test_third_source_reconciliation_is_not_final(self):
        base={"date":"2026-11-08","league":"en.1","home":"Man City",
              "away":"Wolves","home_goals":2,"away_goals":1}
        alias={"en.1":{norm("Man City"):"Manchester City",norm("Wolves"):"Wolverhampton Wanderers"}}
        third={**base,"home":"Manchester City FC","away":"Wolverhampton Wanderers FC"}
        ok=reconcile_staged_with_third([base],[third],"2026-11-21",alias)
        self.assertEqual(ok["verified_count"],1)
        self.assertEqual(ok["status"],"PROVISIONAL_MATCH_UNAUDITED")
        self.assertEqual(ok["verified"][0]["third_source_status"],"SCORE_MATCH_PROVENANCE_UNAUDITED")
        self.assertFalse(ok["ex_final_allowed"])
        third["away_goals"]=0
        bad=reconcile_staged_with_third([base],[third],"2026-11-21",alias)
        self.assertEqual(bad["conflict_count"],1)
        self.assertEqual(bad["status"],"CONFLICT")
        self.assertEqual(reconcile_staged_with_third([base],[],"2026-11-21",alias)["unresolved_count"],1)

    def test_secondary_only_staging_excludes_verified_archive_and_future(self):
        rows=[
            {"date":day,"league":"en.1","home":"A","away":"B","home_goals":1,"away_goals":0}
            for day in ("2026-09-20","2026-11-08","2026-11-21")
        ]
        staged=secondary_only_after_cutoff(rows,"2026-09-20","2026-11-21")
        self.assertEqual(len(staged),1)
        self.assertEqual(staged[0]["date"],"2026-11-08")
        self.assertEqual(staged[0]["verification_status"],"SECONDARY_ONLY_UNVERIFIED")

    def test_premier_reviewed_alias_config(self):
        from pathlib import Path
        import json
        from ex_cross_verify import norm
        mapping=json.loads((Path(__file__).resolve().parents[1] /
                            "config/premier_reviewed_aliases.json").read_text())
        reviewed={"en.1":{norm(k):v for k,v in mapping["en.1"].items()}}
        primary=[{"date":"2026-11-18","league":"en.1","home":"Manchester City FC",
                  "away":"Wolverhampton Wanderers FC","home_goals":2,"away_goals":1}]
        secondary=[{"date":"2026-11-18","league":"en.1","home":"Man City",
                    "away":"Wolves","home_goals":2,"away_goals":1}]
        self.assertEqual(verify(primary,secondary,"2026-11-21",reviewed)["status"],"VERIFIED")
        primary.append({"date":"2026-11-19","league":"en.1","home":"Leeds United FC",
                        "away":"Arsenal FC","home_goals":0,"away_goals":1})
        secondary.append({"date":"2026-11-19","league":"en.1","home":"Leeds",
                          "away":"Arsenal","home_goals":0,"away_goals":1})
        self.assertEqual(verify(primary,secondary,"2026-11-21",reviewed)["matched"],2)
        secondary[0]["away_goals"]=2
        self.assertEqual(verify(primary,secondary,"2026-11-21",reviewed)["status"],"CONFLICT")

    def test_unverified_alias_candidate_is_not_confirmed(self):
        primary=[{"date":"2026-11-18","league":"en.1","home":"A FC",
                  "away":"B FC","home_goals":2,"away_goals":1}]
        secondary=[{"date":"2026-11-18","league":"en.1","home":"Alpha",
                    "away":"Beta","home_goals":2,"away_goals":1}]
        result=verify(primary,secondary,"2026-11-21")
        self.assertEqual(result["matched"],0)
        self.assertEqual(result["alias_suggestion_count"],1)
        self.assertEqual(result["unmatched_details"][0]["reason"],"not_found")
        self.assertEqual(result["alias_suggestions"][0]["status"],"REVIEW_REQUIRED")

    def test_common_club_suffixes(self):
        self.assertEqual(norm("Liverpool FC"),norm("Liverpool"))
        self.assertEqual(norm("AFC Bournemouth"),norm("Bournemouth"))
        self.assertEqual(norm("Chelsea F.C."),norm("Chelsea F.C."))
        self.assertEqual(norm("Manchester City FC"),norm("Manchester City"))

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
        reverse={"en.1":{norm("Manchester United"):"Man United",norm("Wolverhampton Wanderers"):"Wolves"}}
        self.assertEqual(verify(primary,secondary,"2026-11-21",reverse)["status"],"VERIFIED")

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
