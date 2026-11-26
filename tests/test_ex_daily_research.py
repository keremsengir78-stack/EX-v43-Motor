import datetime as dt
import unittest

from ex_cross_verify import norm
from ex_daily_official import key
from ex_daily_research import daily_analysis
from ex_decision import MARKETS
from ex_history_archive import utc


class DailyResearchTests(unittest.TestCase):
    def test_ucl_domestic_archive_remains_separate_from_prospective_calibration(self):
        cutoff = utc("2026-11-25T09:00:00Z")
        kickoff = utc("2026-11-25T20:00:00Z")
        fixture = {"league": "UCL", "home": "Club A", "away": "Club B",
                   "date": "2026-11-25", "kickoff_at": kickoff.isoformat()}
        teams = {norm("Club A"): "Club A", norm("Club B"): "Club B"}
        leagues = {"Club A": "en.1", "Club B": "de.1"}
        rows = []
        for year in (2025, 2026):
            for index in range(1, 11):
                date = dt.date(year, 9, index)
                rows += [{"date": date, "league": "en.1", "home": "Club A", "away": "other", "hg": 2, "ag": 1},
                         {"date": date, "league": "de.1", "home": "other", "away": "Club B", "hg": 1, "ag": 2}]
        fixture_scope = {(kickoff, "Club A", "Club B")}
        snapshot = rows, [], teams, leagues, fixture_scope
        result = daily_analysis(fixture, None, snapshot, cutoff)
        self.assertEqual("UNCALIBRATED_CROSS_LEAGUE_BASELINE", result["domestic_research"]["status"])
        self.assertTrue(result["tur2"])
        self.assertIsNone(result["calibration_cohort"])
        self.assertEqual(set(MARKETS), set(result["markets"]["markets"]))
        self.assertTrue(all(m["ex_g"]["probability"] is None for m in result["markets"]["markets"].values()))
        self.assertFalse(result["auto_control"]["ex_final_allowed"])
        self.assertNotIn("pup:unverified", result["auto_control"]["issues"])
        self.assertEqual("NOT_REQUESTED", result["markets"]["pup"]["status"])
        self.assertIsNone(daily_analysis({**fixture, "home": "Different"}, None, snapshot, cutoff)["domestic_research"])

    def test_official_aliases_preserve_date_and_orientation(self):
        match = key("en.1", "2026-11-25", "Manchester United", "Spurs")
        self.assertEqual(match, key("en.1", "2026-11-25", "Man United", "Tottenham"))
        self.assertNotEqual(match, key("en.1", "2026-11-25", "Tottenham", "Man United"))
        self.assertNotEqual(match, key("en.1", "2026-11-26", "Man United", "Tottenham"))

    def test_rolling_history_uses_ids_and_actual_seasons_after_matchday_five(self):
        cutoff = utc("2027-02-16T13:00:00Z")
        fixture = {"league": "UCL", "home": "Changed brand A", "away": "Changed brand B",
                   "date": "2027-02-16", "kickoff_at": "2027-02-16T20:00:00Z",
                   "team_ids": {"home": "123", "away": "456"}}
        by_team = {}
        for team, league, side in (("123", "eng.1", "home"), ("456", "ger.1", "away")):
            games = []
            for year in (2025, 2026):
                for index in range(10, 0, -1):
                    kickoff = utc(f"{year}-09-{index:02}T12:00:00Z")
                    teams = {side: team, "home" if side == "away" else "away": f"other{index}"}
                    games.append({"kickoff": kickoff, "finished": kickoff + dt.timedelta(hours=2),
                                  "captured_at": kickoff + dt.timedelta(hours=3),
                                  "competition": league, "teams": teams, "score": (2, 1)})
            games.append({**games[-1], "captured_at": cutoff, "score": (20, 20),
                          "kickoff": utc("2027-02-13T12:00:00Z")})
            by_team[team] = games
        row = daily_analysis(fixture, None, None, cutoff, by_team=by_team)
        result = row["domestic_research"]
        self.assertEqual("ROLLING_DOMESTIC_PROVIDER_TEAM_ID", result["history_scope"])
        self.assertEqual({"home": "en.1", "away": "de.1"}, result["domestic_leagues"])
        self.assertEqual("2026-09-10", result["samples"]["home"]["match_dates"][0][-1])
        self.assertTrue(row["tur2"])
        self.assertIsNone(row["calibration_cohort"])
        for game in by_team["456"]:
            game["competition"] = "eng.1"
        domestic = daily_analysis({**fixture, "league": "en.1"}, None, None, cutoff, by_team=by_team)
        self.assertEqual("UNCALIBRATED_SAME_LEAGUE_BASELINE", domestic["domestic_research"]["status"])
        self.assertTrue(domestic["domestic_research"]["baseline"]["top_scores"])
        self.assertTrue(domestic["tur2"])
        self.assertFalse(domestic["ex_final_allowed"])

    def test_official_fixture_and_odds_checks_are_market_scoped(self):
        cutoff = utc("2026-11-25T13:00:00Z")
        board = {"url": "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard?dates=20261125",
                 "retrieved_at": "2026-11-25T12:59:00Z", "sha256": "1" * 64}
        fixture = {"league": "UCL", "home": "Sabah FK", "away": "Barcelona", "date": "2026-11-25",
                   "kickoff_at": "2026-11-25T17:45:00Z", "fixture_source": board["url"],
                   "fixture_checked_at": board["retrieved_at"]}
        quotes = [{"market": "MS1", "bookmaker": "DraftKings", "decimal_odds": 2,
                   "observed_at": board["retrieved_at"], "source": board["url"]}]
        row = daily_analysis(fixture, None, None, cutoff, quotes=quotes, board_evidence=board)
        self.assertEqual("FIXTURE_CROSS_VERIFIED", row["fixture_evidence"]["status"])
        self.assertNotIn("odds_lock:blocked", row["auto_control_by_market"]["MS1"]["issues"])
        self.assertIn("odds_lock:blocked", row["auto_control_by_market"]["KG_VAR"]["issues"])
        self.assertNotIn("fixture_sources:unverified", row["auto_control_by_market"]["MS1"]["issues"])
        self.assertIn("second_source:unverified", row["auto_control_by_market"]["MS1"]["issues"])
        self.assertFalse(row["auto_control_by_market"]["MS1"]["ex_final_allowed"])
        low = daily_analysis(fixture, None, None, cutoff, board_evidence=board,
                             quotes=[{**quotes[0], "decimal_odds": 1.19}])
        self.assertIn("odds_lock:pass_1_19_or_lower", low["auto_control_by_market"]["MS1"]["issues"])
        self.assertNotIn("odds_lock:pass_1_19_or_lower", low["auto_control_by_market"]["KG_VAR"]["issues"])
        reversed_fixture = {**fixture, "home": "Barcelona", "away": "Sabah FK"}
        rejected = daily_analysis(reversed_fixture, None, None, cutoff, board_evidence=board)
        self.assertEqual("UNVERIFIED", rejected["fixture_evidence"]["status"])

    def test_cup_alias_requires_reviewed_team_ids_names_and_orientation(self):
        from ex_daily_research import corroborated_fixture

        cutoff = utc("2026-11-26T09:00:00Z")
        kickoff = utc("2026-11-26T20:00:00Z")
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard?dates=20261126"
        board = {"url": url, "retrieved_at": "2026-11-26T08:59:00Z"}
        fixture = {"league": "UEL", "event_id": "401915505", "home": "NEC Nijmegen",
                   "away": "Stade Rennais", "team_ids": {"home": "147", "away": "169"},
                   "date": "2026-11-26", "kickoff_at": kickoff.isoformat(),
                   "fixture_source": url, "fixture_checked_at": board["retrieved_at"]}
        meta = {"retrieved_at": "2026-11-26T08:58:00Z"}
        evidence = ({(kickoff, "necnijmegen", "rennes")}, meta)
        result = corroborated_fixture(fixture, board, cutoff, evidence)
        self.assertEqual("FIXTURE_CROSS_VERIFIED", result["status"])
        self.assertIn("identity_reviews", result)
        self.assertEqual("FIXTURE_CROSS_VERIFIED", corroborated_fixture(
            {**fixture, "event_id": "new-event"}, board, cutoff, evidence)["status"])
        for changed in ({"team_ids": {"home": "169", "away": "147"}},
                        {"away": "Different Club"}, {"kickoff_at": "2026-11-26T19:00:00Z"}):
            self.assertEqual("UNVERIFIED", corroborated_fixture(
                {**fixture, **changed}, board, cutoff, evidence)["status"])

    def test_reviewed_conference_names_use_the_same_normalization_as_scoreboards(self):
        from ex_team_identity import team_identities

        identities = team_identities()
        for club, display, uefa in (
            ("139", "Ajax Amsterdam", "Ajax"), ("3024", "FC Thun", "Thun"),
            ("126", "SC Freiburg", "Freiburg"), ("152", "FC Twente", "Twente"),
        ):
            with self.subTest(club=club):
                self.assertEqual(norm(display), norm(identities[club]["espn_name"]))
                self.assertEqual(norm(uefa), identities[club]["uefa_alias"])

    def test_quote_fallback_is_market_scoped_and_does_not_substitute_line(self):
        from run_ex_prospective_pipeline import market_quote_chain

        source = {"url": "https://site.api.espn.com/scoreboard",
                  "retrieved_at": "2026-11-26T08:59:00Z", "sha256": "1" * 64}
        provider = {"name": "Example sportsbook"}
        price = {"odds": "+110"}
        board = [{"provider": provider, "moneyline": {"home": {"close": price}}}]
        summary = {"odds": [{"provider": provider, "total": {"over": {"close": {**price, "line": "o3.5"}}}}],
                   "pickcenter": [{"provider": provider, "total": {"over": {"close": {**price, "line": "o2.5"}}}}]}
        offers, attempts = market_quote_chain(board, source, summary, source, "2026-11-26T20:00:00Z")
        self.assertEqual(["MS1", "2.5_UST"], [offer["market"] for offer in offers])
        self.assertNotIn("MS1", attempts[-1]["requested_markets"])
        self.assertEqual([], attempts[1]["found_markets"])
        self.assertEqual("WRONG_TOTAL_LINE", attempts[1]["unresolved"]["2.5_UST"])
        self.assertEqual(["2.5_UST"], attempts[-1]["found_markets"])

    def test_official_briefing_fallback_rechecks_dated_fixture_and_records_failure(self):
        from run_ex_prospective_pipeline import cup_fixture_chain

        class FakeArchive:
            def get(self, url, parse, **kwargs):
                if "briefing" not in url:
                    return parse(b"bad primary page", None), {"url": url}
                raw = (b'<p>All kick-offs 21:00 CET unless stated</p>'
                       b'<p><b>Thursday 26 November 2026</b><br/>'
                       b'<a href="https://www.uefa.com/uefaeuropaleague/match/123--home-vs-away/">'
                       b'Home vs Away</a> (18:45 CET)</p>')
                return parse(raw, None), {"url": url}

        evidence, errors = cup_fixture_chain(FakeArchive(), "UEL", "2026-11-26", 1)
        self.assertEqual({(utc("2026-11-26T17:45:00Z"), "home", "away")}, evidence[0])
        self.assertIn("briefing", evidence[1]["url"])
        self.assertEqual(1, len(errors))
        evidence, errors = cup_fixture_chain(FakeArchive(), "UEL", "2026-11-26", 2)
        self.assertIsNone(evidence)
        self.assertEqual(2, len(errors))

    def test_quote_at_analysis_cutoff_cannot_prevent_valid_fallback(self):
        from run_ex_prospective_pipeline import market_quote_chain

        cutoff = utc("2026-11-26T09:00:00Z")
        source = {"url": "https://site.api.espn.com/scoreboard",
                  "retrieved_at": cutoff.isoformat(), "sha256": "1" * 64}
        offer = [{"provider": {"name": "Example sportsbook"},
                  "total": {"over": {"close": {"line": "o2.5", "odds": "+110"}}}}]
        summary_source = {**source, "retrieved_at": "2026-11-26T08:59:00Z"}
        quotes, attempts = market_quote_chain(offer, source, {"pickcenter": offer}, summary_source,
                                             "2026-11-26T20:00:00Z", as_of=cutoff)
        self.assertEqual([summary_source["retrieved_at"]], [q["observed_at"] for q in quotes])
        self.assertEqual("TIMESTAMP_OUTSIDE_ANALYSIS", attempts[0]["unresolved"]["2.5_UST"])
        self.assertEqual("EMPTY_PAYLOAD", attempts[1]["unresolved"]["2.5_UST"])

    def test_upstream_acceptance_is_bound_to_fixture_and_decision_cutoff(self):
        cutoff = utc("2026-11-26T09:00:00Z")
        kickoff = utc("2026-11-26T20:00:00Z")
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.europa/scoreboard?dates=20261126"
        board = {"url": url, "retrieved_at": "2026-11-26T08:50:00Z"}
        fixture = {"league": "UEL", "event_id": "event-a", "home": "Home", "away": "Away",
                   "team_ids": {"home": "8001", "away": "8002"}, "date": "2026-11-26",
                   "kickoff_at": kickoff.isoformat(), "fixture_source": url,
                   "fixture_checked_at": board["retrieved_at"]}
        evidence = ({(kickoff, "home", "away")}, {"retrieved_at": "2026-11-26T08:51:00Z"})
        reviewed = {"fixture": fixture, "accepted_at": "2026-11-26T08:55:00Z"}
        ingestion = {**reviewed, "status": "INGESTED_CROSS_VERIFIED", "independent_sources_confirmed": 2}
        context = {**reviewed, "status": "CONTEXT_CROSS_VERIFIED"}
        checked = daily_analysis(fixture, None, None, cutoff, board_evidence=board, cup_evidence=evidence,
                                 ingestion_review=ingestion, context_review=context)
        for issues in [checked["auto_control"]["issues"],
                       *(item["issues"] for item in checked["auto_control_by_market"].values())]:
            self.assertNotIn("ingestion:blocked", issues)
            self.assertNotIn("second_source:unverified", issues)
            self.assertNotIn("context:unverified", issues)
            self.assertIn("exg:uncalibrated", issues)
        self.assertFalse(checked["ex_final_allowed"])
        blocked = daily_analysis(fixture, None, None, cutoff, board_evidence=board,
                                 ingestion_review=ingestion,
                                 context_review={**context, "accepted_at": cutoff.isoformat()})
        for reason in ("fixture_sources:unverified", "ingestion:blocked", "context:unverified"):
            self.assertIn(reason, blocked["auto_control"]["issues"])
        reversed_review = {**ingestion, "fixture": {**fixture, "team_ids": {"home": "8002", "away": "8001"}}}
        blocked = daily_analysis(fixture, None, None, cutoff, board_evidence=board, cup_evidence=evidence,
                                 ingestion_review=reversed_review, observations={"roster_payload_observed": True})
        self.assertIn("ingestion:blocked", blocked["auto_control"]["issues"])
        self.assertIn("context:unverified", blocked["auto_control"]["issues"])

    def test_official_domestic_review_requires_exact_board_identity_and_preanalysis_review(self):
        from ex_daily_research import corroborated_fixture, reviewed_fixture_calendars

        review = reviewed_fixture_calendars()["2026-11-27"]["de.1"]
        approved = utc(review["reviewed_at"])
        board = {"url": "https://site.api.espn.com/scoreboard", "sha256": "a" * 64,
                 "retrieved_at": (approved - dt.timedelta(minutes=1)).isoformat()}
        fixture = {**review["fixtures"][0], "date": "2026-11-27", "league": "de.1",
                   "fixture_source": board["url"], "fixture_checked_at": board["retrieved_at"]}
        as_of = approved + dt.timedelta(minutes=1)
        accepted = corroborated_fixture(fixture, board, as_of)
        self.assertEqual("FIXTURE_CROSS_VERIFIED", accepted["status"])
        self.assertEqual("FIXTURE_IDENTITY_ONLY", accepted["scope"])
        self.assertEqual(review["url"], accepted["sources"][1]["url"])
        self.assertEqual("UNVERIFIED", corroborated_fixture(fixture, board, approved)["status"])
        self.assertEqual("UNVERIFIED", corroborated_fixture(fixture, dict(board, sha256=""), as_of)["status"])
        for change in ({"event_id": "different"}, {"league": "de.2"}, {"home": fixture["away"]},
                       {"team_ids": dict(home=fixture["team_ids"]["away"], away=fixture["team_ids"]["home"])},
                       {"kickoff_at": (utc(fixture["kickoff_at"]) + dt.timedelta(minutes=1)).isoformat()}):
            self.assertEqual("UNVERIFIED", corroborated_fixture({**fixture, **change}, board, as_of)["status"])

    def test_weekend_official_calendar_uses_each_fixtures_own_time(self):
        from unittest.mock import patch
        from ex_daily_research import reviewed_fixture_calendars, reviewed_fixture_source

        day, league = "2026-11-28", "no.1"
        review = reviewed_fixture_calendars()[day][league]
        board = {"url": "https://site.api.espn.com/scoreboard", "sha256": "a" * 64}
        as_of = utc(review["reviewed_at"]) + dt.timedelta(minutes=1)
        self.assertGreater(len({row["official_local_time"] for row in review["fixtures"]}), 1)
        for row in review["fixtures"]:
            self.assertIsNotNone(reviewed_fixture_source({**row, "date": day, "league": league}, board, as_of))
        first, second = review["fixtures"]
        wrong = {**first, "official_local_time": second["official_local_time"]}
        with patch("ex_daily_research.reviewed_fixture_calendars",
                   return_value={day: {league: {**review, "fixtures": [wrong, second]}}}):
            self.assertIsNone(reviewed_fixture_source({**first, "date": day, "league": league}, board, as_of))
