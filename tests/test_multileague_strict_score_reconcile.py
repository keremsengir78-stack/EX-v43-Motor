import unittest
from unittest.mock import patch
from ex_multileague_strict_score_reconcile import reconcile, validate_club_identities, CLUB_IDENTITIES

class StrictScoreReconcileTests(unittest.TestCase):
    def setUp(self):
        self.fixture={"league":"en.1","season":"2025-26","date":"2025-08-16",
                      "home":"Aston Villa FC","away":"Newcastle United FC"}
        self.batches={"ex_final_allowed":False,"batches":[{"fixtures":[self.fixture]}]}
        self.primary=[{"date":"2025-08-16","league":"en.1","season":"2025-26",
                       "home":"Aston Villa FC","away":"Newcastle United FC","hg":0,"ag":0}]
        self.secondary=[{"date":"2025-08-16","league":"en.1",
                         "home":"Aston Villa","away":"Newcastle United","home_goals":0,"away_goals":0}]
        self.meta={"provider":"football-data.co.uk","url":"https://example.org/secondary.csv","sha256":"abc"}

    def test_exact_match_with_equal_scores(self):
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual((result["confirmed"],result["remaining"]),(1,0))
        self.assertFalse(result["ex_final_allowed"])

    def test_conflicting_score_stays_pending(self):
        self.secondary[0]["away_goals"]=1
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],0)
        self.assertEqual(result["reasons"],{"SCORE_CONFLICT":1})

    def test_ambiguous_secondary_stays_pending(self):
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary*2,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],0)
        self.assertEqual(result["reasons"],{"SECONDARY_MISSING_OR_AMBIGUOUS":1})

    def test_source_failure_stays_pending(self):
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=([],{"error":"timeout"})):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["reasons"],{"SECONDARY_SOURCE_ERROR":1})

    def test_standalone_club_suffixes_are_equivalent(self):
        self.fixture.update({"league":"es.1","home":"Levante UD","away":"FC Barcelona"})
        self.primary[0].update({"league":"es.1","home":"Levante UD","away":"FC Barcelona","hg":2,"ag":3})
        self.secondary[0].update({"league":"es.1","home":"Levante","away":"Barcelona","home_goals":2,"away_goals":3})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_similar_but_different_clubs_are_not_equivalent(self):
        self.secondary[0]["away"]="Newcastle City"
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],0)

    def test_normalized_primary_collision_is_rejected(self):
        self.primary.append(dict(self.primary[0],home="Aston Villa",away="Newcastle United"))
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],0)
        self.assertEqual(result["reasons"],{"PRIMARY_MISSING_OR_AMBIGUOUS":1})

    def test_duplicate_fixture_claim_is_rejected(self):
        self.batches["batches"][0]["fixtures"].append(dict(self.fixture))
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)
        self.assertEqual(result["reasons"],{"DUPLICATE_CLAIM":1})

    def test_english_club_identity_is_scoped_and_score_checked(self):
        self.secondary[0]["away"]="Newcastle"
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_italian_club_identity_is_scoped_and_score_checked(self):
        self.fixture.update({"league":"it.1","home":"FC Internazionale Milano","away":"Torino FC"})
        self.primary[0].update({"league":"it.1","home":"FC Internazionale Milano","away":"Torino FC"})
        self.secondary[0].update({"home":"Inter","away":"Torino"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_leeds_identity_against_provider_short_name(self):
        self.fixture.update({"home":"Leeds United FC","away":"Everton FC"})
        self.primary[0].update({"home":"Leeds United FC","away":"Everton FC"})
        self.secondary[0].update({"home":"Leeds","away":"Everton"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_spanish_club_identity_with_equal_score(self):
        self.fixture.update({"league":"es.1","home":"RCD Mallorca","away":"FC Barcelona"})
        self.primary[0].update({"league":"es.1","home":"RCD Mallorca","away":"FC Barcelona"})
        self.secondary[0].update({"home":"Mallorca","away":"Barcelona"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_italian_club_identity_with_equal_score(self):
        self.fixture.update({"league":"it.1","home":"Genoa CFC","away":"Juventus FC"})
        self.primary[0].update({"league":"it.1","home":"Genoa CFC","away":"Juventus FC"})
        self.secondary[0].update({"home":"Genoa","away":"Juventus"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_italian_fiorentina_prefix_with_equal_score(self):
        self.fixture.update({"league":"it.1","home":"Torino FC","away":"ACF Fiorentina"})
        self.primary[0].update({"league":"it.1","home":"Torino FC","away":"ACF Fiorentina"})
        self.secondary[0].update({"home":"Torino","away":"Fiorentina"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_spanish_athletic_provider_abbreviation_with_equal_score(self):
        self.fixture.update({"league":"es.1","home":"Athletic Club","away":"Sevilla FC"})
        self.primary[0].update({"league":"es.1","home":"Athletic Club","away":"Sevilla FC"})
        self.secondary[0].update({"home":"Ath Bilbao","away":"Sevilla"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_remaining_spanish_real_betis_name(self):
        self.fixture.update({"league":"es.1","home":"Real Betis Balompié","away":"Sevilla FC"})
        self.primary[0].update({"league":"es.1","home":"Real Betis Balompié","away":"Sevilla FC"})
        self.secondary[0].update({"home":"Betis","away":"Sevilla"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_remaining_italian_atalanta_name(self):
        self.fixture.update({"league":"it.1","home":"Atalanta BC","away":"AC Milan"})
        self.primary[0].update({"league":"it.1","home":"Atalanta BC","away":"AC Milan"})
        self.secondary[0].update({"home":"Atalanta","away":"Milan"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_remaining_english_coventry_name(self):
        self.fixture.update({"home":"Coventry City FC","away":"Arsenal FC"})
        self.primary[0].update({"home":"Coventry City FC","away":"Arsenal FC"})
        self.secondary[0].update({"home":"Coventry","away":"Arsenal"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)

    def test_club_alias_table_has_no_chains(self):
        validate_club_identities()

    def test_chained_alias_is_rejected(self):
        with patch.dict(CLUB_IDENTITIES["en.1"],{"newcastle":"otherclub"}):
            with self.assertRaisesRegex(ValueError,"chained club alias"):
                validate_club_identities()

    def test_spanish_provider_vallecano_short_name(self):
        self.fixture.update({"league":"es.1","home":"Rayo Vallecano de Madrid","away":"FC Barcelona"})
        self.primary[0].update({"league":"es.1","home":"Rayo Vallecano de Madrid","away":"FC Barcelona"})
        self.secondary[0].update({"home":"Vallecano","away":"Barcelona"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            self.assertEqual(reconcile(self.batches,self.primary)["confirmed"],1)

    def test_italian_provider_monza_short_name(self):
        self.fixture.update({"league":"it.1","home":"AC Monza","away":"Frosinone Calcio"})
        self.primary[0].update({"league":"it.1","home":"AC Monza","away":"Frosinone Calcio"})
        self.secondary[0].update({"home":"Monza","away":"Frosinone"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            self.assertEqual(reconcile(self.batches,self.primary)["confirmed"],1)

    def test_racing_santander_provider_name_requires_equal_score(self):
        self.fixture.update({"league":"es.1","home":"Real Racing Club de Santander","away":"Villarreal CF"})
        self.primary[0].update({"league":"es.1","home":"Real Racing Club de Santander","away":"Villarreal CF"})
        self.secondary[0].update({"home":"Santander","away":"Villarreal"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            self.assertEqual(reconcile(self.batches,self.primary)["confirmed"],1)
        self.secondary[0]["away_goals"]=2
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            self.assertEqual(reconcile(self.batches,self.primary)["reasons"],{"SCORE_CONFLICT":1})

    def test_deportivo_la_coruna_provider_name(self):
        self.fixture.update({"league":"es.1","home":"RC Deportivo La Coruña","away":"Sevilla FC"})
        self.primary[0].update({"league":"es.1","home":"RC Deportivo La Coruña","away":"Sevilla FC"})
        self.secondary[0].update({"home":"La Coruna","away":"Sevilla"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            self.assertEqual(reconcile(self.batches,self.primary)["confirmed"],1)

    def test_conflicting_same_day_fixture_keeps_final_locked_and_exposes_evidence(self):
        self.fixture.update({"league":"es.1","home":"FC Barcelona","away":"Real Racing Club de Santander"})
        self.primary[0].update({"league":"es.1","home":"FC Barcelona","away":"Real Racing Club de Santander"})
        self.secondary[0].update({"home":"Barcelona","away":"Sevilla"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],0)
        self.assertEqual(result["remaining"],1)
        self.assertFalse(result["ex_final_allowed"])
        self.assertEqual(result["unresolved"][0]["reason"],"SECONDARY_SAME_DAY_SHARED_TEAM")
        self.assertEqual(result["unresolved"][0]["source_diagnostic"]["shared_team_alternatives"][0]["away"],"Sevilla")

    def test_german_paderborn_identity_requires_exact_score(self):
        self.fixture.update({"league":"de.1","home":"1. FSV Mainz 05","away":"SC Paderborn 07"})
        self.primary[0].update({"league":"de.1","home":"1. FSV Mainz 05","away":"SC Paderborn 07"})
        self.secondary[0].update({"league":"de.1","home":"1. FSV Mainz 05","away":"Paderborn"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],1)
        self.assertFalse(result["ex_final_allowed"])
        self.secondary[0]["away_goals"]=3
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["reasons"],{"SCORE_CONFLICT":1})

    def test_german_elversberg_identity_is_league_scoped(self):
        self.fixture.update({"league":"de.1","home":"SV 07 Elversberg","away":"Bayer 04 Leverkusen"})
        self.primary[0].update({"league":"de.1","home":"SV 07 Elversberg","away":"Bayer 04 Leverkusen"})
        self.secondary[0].update({"league":"de.1","home":"Elversberg","away":"Bayer 04 Leverkusen"})
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            self.assertEqual(reconcile(self.batches,self.primary)["confirmed"],1)
        self.fixture["league"]="en.1"
        self.primary[0]["league"]="en.1"
        self.secondary[0]["league"]="en.1"
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            self.assertEqual(reconcile(self.batches,self.primary)["confirmed"],0)

    def test_german_real_provider_opponent_abbreviations(self):
        pairs=[
            ("1. FSV Mainz 05","SC Paderborn 07","Mainz","Paderborn"),
            ("SV 07 Elversberg","Bayer 04 Leverkusen","Elversberg","Leverkusen"),
            ("Borussia Mönchengladbach","SV 07 Elversberg","M'gladbach","Elversberg"),
            ("SC Paderborn 07","SC Freiburg","Paderborn","Freiburg"),
            ("Borussia Dortmund","SC Paderborn 07","Dortmund","Paderborn"),
            ("SV 07 Elversberg","FC Bayern München","Elversberg","Bayern Munich"),
            ("FC Schalke 04","SV 07 Elversberg","Schalke 04","Elversberg"),
            ("SC Paderborn 07","TSG 1899 Hoffenheim","Paderborn","Hoffenheim"),
        ]
        for home,away,short_home,short_away in pairs:
            with self.subTest(home=home,away=away):
                self.fixture.update({"league":"de.1","home":home,"away":away})
                self.primary[0].update({"league":"de.1","home":home,"away":away})
                self.secondary[0].update({"league":"de.1","home":short_home,"away":short_away})
                with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
                    result=reconcile(self.batches,self.primary)
                self.assertEqual(result["confirmed"],1)
                self.assertFalse(result["ex_final_allowed"])

    def test_wrong_season_cannot_confirm(self):
        self.primary[0]["season"]="2024-25"
        with patch("ex_multileague_strict_score_reconcile.secondary_rows",return_value=(self.secondary,self.meta)):
            result=reconcile(self.batches,self.primary)
        self.assertEqual(result["confirmed"],0)
        self.assertEqual(result["reasons"],{"PRIMARY_MISSING_OR_AMBIGUOUS":1})

    def test_unapproved_batches_fail_closed(self):
        self.batches["ex_final_allowed"]=True
        with self.assertRaises(ValueError):
            reconcile(self.batches,self.primary)

if __name__=="__main__":
    unittest.main()
