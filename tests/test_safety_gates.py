"""Dependency-light safety regression for the three EX v4.3 decision gates."""
import unittest

from ex_auto_control import auto_control
from ex_decision import weighted_evidence
from ex_fixture_odds import check_fixture, check_odds


class SafetyGates(unittest.TestCase):
    def test_exg_is_never_a_calibrated_probability(self):
        features={name:{"score":0.8,"verified":True,"source":"audit",
                        "timestamp":"2026-11-21T09:00:00Z"}
                  for name in ("team_strength","match_conditions","external_factors")}
        result=weighted_evidence(features,as_of="2026-11-22")
        self.assertEqual(result["status"],"EVIDENCE_COMPLETE_UNCALIBRATED")
        self.assertIsNone(result["calibrated_probability"])
        self.assertFalse(result["ex_final_allowed"])

    def test_exg_weighted_contributions_are_independent_of_final_probability(self):
        features={
            "team_strength":{"score":0.8,"verified":True,"source":"audit","timestamp":"2026-11-21T09:00:00Z"},
            "match_conditions":{"score":0.6,"verified":True,"source":"audit","timestamp":"2026-11-21T09:00:00Z"},
            "external_factors":{"score":0.5,"verified":True,"source":"audit","timestamp":"2026-11-21T09:00:00Z"},
        }
        result=weighted_evidence(features,as_of="2026-11-22")
        self.assertEqual(result["contributions"],{
            "team_strength":0.4,"match_conditions":0.18,"external_factors":0.1})
        self.assertAlmostEqual(result["weighted_score"],0.68)
        self.assertEqual(result["status"],"EVIDENCE_COMPLETE_UNCALIBRATED")
        self.assertIsNone(result["calibrated_probability"])
        self.assertFalse(result["ex_final_allowed"])

    def test_exg_rejects_noncanonical_analysis_dates(self):
        features={name:{"score":0.8,"verified":True,"source":"audit",
                        "timestamp":"2026-11-21T09:00:00Z"}
                  for name in ("team_strength","match_conditions","external_factors")}
        for cutoff in ("2026-W47-7","20261122","2026-11-2"):
            result=weighted_evidence(features,as_of=cutoff)
            self.assertEqual(result["status"],"BLOCKED")
            self.assertIn("invalid_as_of",result["issues"])
            self.assertFalse(result["ex_final_allowed"])
        self.assertEqual(weighted_evidence(features,as_of="2026-11-22")["status"],
                         "EVIDENCE_COMPLETE_UNCALIBRATED")

    def test_timestamp_cutoffs_reject_iso_week_and_compact_forms(self):
        fixture={"date":"2026-11-22","league":"test","home":"A","away":"B",
                 "fixture_source":"official","fixture_checked_at":"2026-11-21T09:00:00Z",
                 "kickoff_at":"2026-11-22T15:00:00Z"}
        odds={"decimal_odds":1.5,"market":"KG_VAR","bookmaker":"audit",
              "source":"audit","observed_at":"2026-11-21T09:00:00Z"}
        features={name:{"score":0.8,"verified":True,"source":"audit",
                        "timestamp":"2026-11-21T09:00:00Z"}
                  for name in ("team_strength","match_conditions","external_factors")}
        for cutoff in ("2026-W47-7T10:00:00Z","20261122T10:00:00Z"):
            self.assertEqual(check_fixture(fixture,cutoff)["status"],"BLOCKED")
            self.assertEqual(check_odds(odds,cutoff)["status"],"BLOCKED")
            self.assertIn("invalid_as_of",weighted_evidence(features,cutoff)["issues"])
        canonical="2026-11-22T10:00:00Z"
        self.assertEqual(check_fixture(fixture,canonical)["status"],"VERIFIED_INPUT")
        self.assertEqual(check_odds(odds,canonical)["status"],"VERIFIED_INPUT")
        self.assertEqual(weighted_evidence(features,canonical)["status"],
                         "EVIDENCE_COMPLETE_UNCALIBRATED")

    def test_fixture_time_boundaries(self):
        fixture={"date":"2026-11-22","league":"test","home":"A","away":"B",
                 "fixture_source":"official","fixture_checked_at":"2026-11-22T09:00:00Z",
                 "kickoff_at":"2026-11-22T15:00:00Z"}
        self.assertEqual(check_fixture(fixture,"2026-11-22T10:00:00Z")["status"],"VERIFIED_INPUT")
        self.assertIn("fixture:analysis_after_kickoff",
                      check_fixture(fixture,"2026-11-22T15:00:00Z")["issues"])
        self.assertEqual(check_fixture(fixture,"2026-11-22T10:00:00")["status"],"BLOCKED")

    def test_fixture_date_follows_kickoff_local_calendar_not_utc(self):
        fixture={"date":"2026-11-23","league":"test","home":"A","away":"B",
                 "fixture_source":"official","fixture_checked_at":"2026-11-22T18:00:00Z",
                 "kickoff_at":"2026-11-23T00:30:00+03:00"}
        # Local fixture date is Nov 23 even though the UTC date is Nov 22.
        result=check_fixture(fixture,"2026-11-22T19:00:00Z")
        self.assertEqual(result["status"],"VERIFIED_INPUT")
        self.assertFalse(result["ex_final_allowed"])
        self.assertIn("kickoff_at:date_mismatch",
                      check_fixture({**fixture,"date":"2026-11-22"},
                                    "2026-11-22T19:00:00Z")["issues"])

    def test_fixture_timestamp_cutoff_uses_instant_not_local_calendar_date(self):
        fixture={"date":"2026-11-22","league":"test","home":"A","away":"B",
                 "fixture_source":"official","fixture_checked_at":"2026-11-22T09:00:00Z",
                 "kickoff_at":"2026-11-22T15:00:00Z"}
        # The same instant is Nov 23 in +14:00, but kickoff is still in the future.
        self.assertEqual(check_fixture(fixture,"2026-11-23T00:00:00+14:00")["status"],
                         "VERIFIED_INPUT")
        # The same instant is Nov 21 in -12:00, but kickoff has already passed.
        fixture["kickoff_at"]="2026-11-22T10:00:00Z"
        result=check_fixture(fixture,"2026-11-21T23:00:00-12:00")
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("fixture:analysis_after_kickoff",result["issues"])

    def test_fixture_verification_at_exact_analysis_instant_is_blocked(self):
        fixture={"date":"2026-11-22","league":"test","home":"A","away":"B",
                 "fixture_source":"official","fixture_checked_at":"2026-11-22T10:00:00Z",
                 "kickoff_at":"2026-11-22T15:00:00Z"}
        cutoff="2026-11-22T10:00:00Z"
        result=check_fixture(fixture,cutoff)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("fixture:verified_after_analysis",result["issues"])
        fixture["fixture_checked_at"]="2026-11-22T09:59:59Z"
        self.assertEqual(check_fixture(fixture,cutoff)["status"],"VERIFIED_INPUT")

    def test_fixture_date_only_cutoff_prevents_lookahead(self):
        fixture={"date":"2026-11-22","league":"test","home":"A","away":"B",
                 "fixture_source":"official","fixture_checked_at":"2026-11-22T09:00:00Z",
                 "kickoff_at":"2026-11-22T15:00:00Z"}
        result=check_fixture(fixture,"2026-11-22")
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("fixture:verified_after_analysis",result["issues"])
        fixture["fixture_checked_at"]="2026-11-21T23:59:59Z"
        self.assertEqual(check_fixture(fixture,"2026-11-22")["status"],"VERIFIED_INPUT")
        fixture["fixture_checked_at"]="2026-11-22T09:00:00Z"
        self.assertEqual(check_fixture(fixture,"2026-11-22T10:00:00Z")["status"],"VERIFIED_INPUT")

    def test_fixture_date_only_cutoff_normalizes_timezone_to_utc(self):
        fixture={"date":"2026-11-22","league":"test","home":"A","away":"B",
                 "fixture_source":"official","fixture_checked_at":"2026-11-22T01:30:00+03:00",
                 "kickoff_at":"2026-11-22T15:00:00Z"}
        # This verification is still on Nov 21 in UTC.
        self.assertEqual(check_fixture(fixture,"2026-11-22")["status"],"VERIFIED_INPUT")
        fixture["fixture_checked_at"]="2026-11-21T23:30:00-03:00"
        # This verification is already Nov 22 in UTC.
        result=check_fixture(fixture,"2026-11-22")
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("fixture:verified_after_analysis",result["issues"])

    def test_fixture_rejects_noncanonical_dates(self):
        fixture={"date":"2026-11-22","league":"test","home":"A","away":"B",
                 "fixture_source":"official","fixture_checked_at":"2026-11-21T09:00:00Z",
                 "kickoff_at":"2026-11-22T15:00:00Z"}
        for invalid in ("20261122","2026-W47-7","2026-11-2"):
            result=check_fixture({**fixture,"date":invalid},"2026-11-22")
            self.assertEqual(result["status"],"BLOCKED")
            self.assertIn("fixture:invalid_date",result["issues"])
        for invalid in ("20261122","2026-W47-7","2026-11-2"):
            result=check_fixture(fixture,invalid)
            self.assertEqual(result["status"],"BLOCKED")
            self.assertIn("fixture:invalid_date",result["issues"])
        self.assertEqual(check_fixture(fixture,"2026-11-22")["status"],"VERIFIED_INPUT")

    def test_odds_threshold_and_future_snapshot(self):
        odds={"decimal_odds":1.19,"market":"KG_VAR","bookmaker":"audit",
              "source":"audit","observed_at":"2026-11-21T09:00:00Z"}
        result=check_odds(odds,"2026-11-22T10:00:00Z")
        self.assertEqual(result["decision"],"PASS_ODDS_1_19_OR_LOWER")
        self.assertFalse(result["ex_final_allowed"])
        odds["decimal_odds"]=1.20
        self.assertEqual(check_odds(odds,"2026-11-22T10:00:00Z")["decision"],"NO_FINAL")
        odds["observed_at"]="2026-11-22T10:00:00Z"
        self.assertEqual(check_odds(odds,"2026-11-22T10:00:00Z")["status"],"BLOCKED")

    def test_invalid_odds_and_unsupported_market_fail_closed(self):
        odds={"decimal_odds":1.5,"market":"KG_VAR","bookmaker":"audit",
              "source":"audit","observed_at":"2026-11-21T09:00:00Z"}
        for value in (float("nan"),float("inf"),True,"1.5",10**10000):
            result=check_odds({**odds,"decimal_odds":value},"2026-11-22T10:00:00Z")
            self.assertEqual(result["status"],"BLOCKED")
            self.assertFalse(result["ex_final_allowed"])
        result=check_odds({**odds,"market":"UNSUPPORTED"},"2026-11-22T10:00:00Z")
        self.assertIn("market:unsupported",result["issues"])

    def test_auto_control_requires_independent_sources(self):
        match={"recompute_consistent":True,"status":"BASELINE_ONLY",
               "fixture_lock":{"status":"VERIFIED_INPUT"},
               "odds_lock":{"status":"VERIFIED_INPUT"},
               "market_baselines_pct":{"2.5_UST":50,"KG_VAR":50,
                                       "MS1":40,"MSX":30,"MS2":30}}
        for count in (0,1,True,"2"):
            ingestion={"status":"INGESTED_CROSS_VERIFIED",
                       "independent_sources_confirmed":count}
            result=auto_control(match,ingestion)
            self.assertIn("second_source:unverified",result["issues"])
            self.assertFalse(result["ex_final_allowed"])

    def test_ingested_but_not_cross_verified_is_blocked(self):
        match={"recompute_consistent":True,"status":"BASELINE_ONLY",
               "fixture_lock":{"status":"VERIFIED_INPUT"},
               "odds_lock":{"status":"VERIFIED_INPUT"},
               "market_baselines_pct":{"2.5_UST":50,"KG_VAR":50,
                                       "MS1":40,"MSX":30,"MS2":30}}
        ingestion={"status":"INGESTED","independent_sources_confirmed":2}
        result=auto_control(match,ingestion)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("ingestion:blocked",result["issues"])
        self.assertFalse(result["ex_final_allowed"])
        ingestion["status"]="INGESTED_CROSS_VERIFIED"
        result=auto_control(match,ingestion)
        self.assertNotIn("ingestion:blocked",result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_auto_control_tur2_and_ingestion_fail_closed(self):
        match={"recompute_consistent":False,"status":"BASELINE_ONLY",
               "fixture_lock":{"status":"VERIFIED_INPUT"},
               "odds_lock":{"status":"VERIFIED_INPUT"},
               "market_baselines_pct":{"2.5_UST":50,"KG_VAR":50,
                                       "MS1":40,"MSX":30,"MS2":30}}
        ingestion={"status":"UNKNOWN","independent_sources_confirmed":2}
        result=auto_control(match,ingestion)
        self.assertIn("tur2:recompute_mismatch",result["issues"])
        self.assertIn("ingestion:blocked",result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_exg_rejects_future_and_nonfinite_evidence(self):
        features={name:{"score":0.8,"verified":True,"source":"audit",
                        "timestamp":"2026-11-21T09:00:00Z"}
                  for name in ("team_strength","match_conditions","external_factors")}
        for invalid in (float("nan"),float("inf"),float("-inf")):
            candidate={key:dict(value) for key,value in features.items()}
            candidate["team_strength"]["score"]=invalid
            result=weighted_evidence(candidate,as_of="2026-11-22")
            self.assertEqual(result["status"],"BLOCKED")
            self.assertIsNone(result["weighted_score"])
        features["team_strength"]["timestamp"]="2026-11-22T01:00:00Z"
        result=weighted_evidence(features,as_of="2026-11-22")
        self.assertIn("team_strength:future_evidence",result["issues"])
        self.assertFalse(result["ex_final_allowed"])

    def test_tur2_snapshot_is_deterministic_and_strict(self):
        from ex_auto_control import snapshot
        original={"status":"BASELINE_ONLY",
                  "market_baselines_pct":{"KG_VAR":55,"MS1":40}}
        reordered={"market_baselines_pct":{"MS1":40,"KG_VAR":55},
                   "status":"BASELINE_ONLY"}
        changed={"status":"BASELINE_ONLY",
                 "market_baselines_pct":{"KG_VAR":56,"MS1":40}}
        self.assertEqual(snapshot(original),snapshot(reordered))
        self.assertNotEqual(snapshot(original),snapshot(changed))
        with self.assertRaises(ValueError):
            snapshot({"bad":float("nan")})

    def test_exg_extreme_integer_scores_fail_closed(self):
        features={name:{"score":0.8,"verified":True,"source":"audit",
                        "timestamp":"2026-11-21T09:00:00Z"}
                  for name in ("team_strength","match_conditions","external_factors")}
        for score in (10**10000,-10**10000):
            features["team_strength"]["score"]=score
            result=weighted_evidence(features,as_of="2026-11-22")
            self.assertEqual(result["status"],"BLOCKED")
            self.assertIn("team_strength:invalid_score",result["issues"])
            self.assertIsNone(result["weighted_score"])
            self.assertFalse(result["ex_final_allowed"])

    def test_auto_control_rejects_non_json_snapshot_objects(self):
        match={"recompute_consistent":True,"status":"BASELINE_ONLY",
               "fixture_lock":{"status":"VERIFIED_INPUT"},
               "odds_lock":{"status":"VERIFIED_INPUT"},
               "market_baselines_pct":{"2.5_UST":50,"KG_VAR":50,
                                       "MS1":40,"MSX":30,"MS2":30},
               "untrusted_metadata":{"arbitrary","unordered"}}
        ingestion={"status":"INGESTED_CROSS_VERIFIED","independent_sources_confirmed":2}
        result=auto_control(match,ingestion)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("snapshot:invalid",result["issues"])
        self.assertIsNone(result["snapshot_sha256"])
        self.assertFalse(result["ex_final_allowed"])

    def test_auto_control_nonfinite_snapshot_rejected(self):
        match={"recompute_consistent":True,"status":"BASELINE_ONLY",
               "fixture_lock":{"status":"VERIFIED_INPUT"},
               "odds_lock":{"status":"VERIFIED_INPUT"},
               "market_baselines_pct":{"2.5_UST":50,"KG_VAR":50,
                                       "MS1":40,"MSX":30,"MS2":30}}
        ingestion={"status":"INGESTED_CROSS_VERIFIED","independent_sources_confirmed":2}
        for bad in (float("nan"),float("inf"),float("-inf")):
            candidate={**match,"market_baselines_pct":{**match["market_baselines_pct"],"KG_VAR":bad}}
            result=auto_control(candidate,ingestion)
            self.assertEqual(result["status"],"BLOCKED")
            self.assertIn("market_baselines:invalid",result["issues"])
            self.assertIn("snapshot:invalid",result["issues"])
            self.assertIsNone(result["snapshot_sha256"])
            self.assertFalse(result["ex_final_allowed"])

    def test_auto_control_extreme_snapshot_does_not_crash(self):
        match={"recompute_consistent":True,"status":"BASELINE_ONLY",
               "fixture_lock":{"status":"VERIFIED_INPUT"},
               "odds_lock":{"status":"VERIFIED_INPUT"},
               "market_baselines_pct":{"2.5_UST":50,"KG_VAR":10**10000,
                                       "MS1":40,"MSX":30,"MS2":30}}
        ingestion={"status":"INGESTED_CROSS_VERIFIED","independent_sources_confirmed":2}
        result=auto_control(match,ingestion)
        self.assertEqual(result["status"],"BLOCKED")
        self.assertIn("market_baselines:invalid",result["issues"])
        self.assertIn("snapshot:invalid",result["issues"])
        self.assertFalse(result["ex_final_allowed"])


if __name__=="__main__":
    unittest.main()
