"""Date-only, odds-free historical inputs shared by domestic and UCL fixtures."""

from bisect import bisect_left
from collections import defaultdict
from datetime import timedelta
from statistics import mean

from ex_decision import MARKETS
from ex_history_archive import utc


def market_labels(home, away):
    return {
        "2.5_UST": int(home + away >= 3), "KG_VAR": int(home > 0 and away > 0),
        "MS1": int(home > away), "MS2": int(home < away),
    }


class HistoricalFeatures:
    def __init__(self, rows):
        fixtures = defaultdict(list)
        for row in sorted(rows, key=lambda r: r["date"]):
            for side, goals, conceded in (("home", "hg", "ag"), ("away", "ag", "hg")):
                fixtures[row["league"], row[side]].append(
                    (row["date"], side, row[goals], row[conceded])
                )
        self.history = {key: ([row[0] for row in games], games) for key, games in fixtures.items()}

    def _side(self, league, team, side, cutoff):
        dates, games = self.history.get((league, team), ([], []))
        end = bisect_left(dates, cutoff)
        venue = [(gf, ga) for _, played_side, gf, ga in games[:end] if played_side == side][-10:]
        labels = {}
        if len(venue) == 10:
            # Orient both clubs' historical fixtures to their role in the target market.
            samples = [market_labels(gf, ga) if side == "home" else market_labels(ga, gf) for gf, ga in venue]
            labels = {market: mean(row[market] for row in samples) for market in MARKETS}
        return {
            "venue_matches": len(venue), "venue_market_frequencies": labels,
            "venue_goal_difference_last_10": mean(gf - ga for gf, ga in venue) if labels else None,
            "venue_goal_difference_last_5": mean(gf - ga for gf, ga in venue[-5:]) if labels else None,
            "last_domestic_result": dates[end - 1].isoformat() if end else None,
            "domestic_rest_calendar_days": (cutoff - dates[end - 1]).days if end else None,
            "domestic_matches_last_14_days": end - bisect_left(dates, cutoff - timedelta(days=14)) if end else None,
        }

    def fixture(self, home_league, away_league, home, away, cutoff):
        return {
            "home": self._side(home_league, home, "home", cutoff),
            "away": self._side(away_league, away, "away", cutoff),
            "external_factors_score": None, "scope": "DOMESTIC_RESULT_OBSERVATIONS",
            "cutoff_date_exclusive": cutoff.isoformat(), "verified_component_scores": False,
        }


def provider_context(calendar, details, as_of):
    """Expose only evidence already captured before this UTC analysis instant."""
    cutoff = utc(as_of)
    if utc(calendar["source"]["retrieved_at"]) >= cutoff:
        return {"status": "SCHEDULE_UNAVAILABLE_AT_CUTOFF"}
    club = calendar["team_id"]
    venue, matched = None, 0
    games = sorted((fixture for fixture in calendar["fixtures"] if fixture["completed"]
                    and utc(fixture["kickoff_at"]) < cutoff), key=lambda fixture: fixture["kickoff_at"])
    last = utc(games[-1]["kickoff_at"]) if games else None
    recent = [fixture for fixture in games if cutoff - utc(fixture["kickoff_at"]) <= timedelta(days=14)]
    observed_minutes, nominal_minutes = {}, {}
    selected = recent or games[-1:]
    for game in selected:
        detail = details.get(game["event_id"])
        if (not detail or not detail["completed"] or detail["teams"] != game["teams"]
                or utc(detail["kickoff_at"]) != utc(game["kickoff_at"])
                or not utc(game["kickoff_at"]) <= utc(detail["source"]["retrieved_at"]) < cutoff):
            continue
        if game is games[-1] and detail.get("venue"):
            venue = {"venue": detail["venue"], "event_id": game["event_id"], "source": detail["source"]}
        if not recent:
            continue
        matched += 1
        for player in detail["player_rows"]:
            if player["team_id"] != club:
                continue
            athlete = player["athlete_id"]
            for field, aggregation in (("provider_minutes", observed_minutes),
                                       ("nominal_regulation_minutes", nominal_minutes)):
                value = player[field]
                if value is not None:
                    aggregation[athlete] = aggregation.get(athlete, 0) + value
    return {"status": "OBSERVED_PROVIDER_COVERAGE", "observed_matches_14d": len(recent),
            "hours_since_last_observed_kickoff": (cutoff - last).total_seconds() / 3600 if last else None,
            "provider_minutes_14d": observed_minutes, "nominal_minutes_14d": nominal_minutes,
            "matched_summaries_14d": matched, "last_observed_venue": venue,
            "complete_schedule_certified": False, "verified_component_scores": False}


class ProviderHistory:
    """Read-only research context for an explicit fixture, at a declared instant."""

    def __init__(self, calendars, details):
        self.calendars = defaultdict(list)
        for calendar in calendars:
            self.calendars[calendar["team_id"]].append(calendar)
        self.details = details

    def fixture(self, teams, kickoff_at, as_of):
        kickoff, cutoff = utc(kickoff_at), utc(as_of)
        if cutoff >= kickoff or set(teams) != {"home", "away"} or teams["home"] == teams["away"]:
            raise ValueError("Invalid fixture teams or prematch cutoff")
        result = {}
        for side, team in teams.items():
            fixtures = {}
            observed = []
            for calendar in self.calendars.get(team, []):
                captured = utc(calendar["source"]["retrieved_at"])
                if captured < cutoff:
                    observed.append(captured)
                    for game in calendar["fixtures"]:
                        if team not in game["teams"].values():
                            raise ValueError("Foreign fixture in team calendar")
                        event_id = game["event_id"]
                        if event_id in fixtures and any(
                            fixtures[event_id][key] != game[key] for key in ("teams", "kickoff_at")
                        ):
                            raise ValueError("Conflicting team calendar identity")
                        if event_id not in fixtures or game["completed"]:
                            fixtures[event_id] = game
            if observed:
                result[side] = provider_context(
                    {"team_id": team, "source": {"retrieved_at": max(observed).isoformat()},
                     "fixtures": list(fixtures.values())}, self.details, as_of,
                )
            else:
                result[side] = {"status": "SCHEDULE_UNAVAILABLE_AT_CUTOFF"}
        return {"sides": result, "as_of": as_of, "scope": "TIMESTAMPED_PROVIDER_OBSERVATIONS",
                "verified_component_scores": False, "ex_final_allowed": False}

    def pregame_coverage(self, events):
        counts = {"targets": 0, "two_calendars": 0, "two_load_histories": 0,
                  "two_minute_histories": 0, "two_venue_histories": 0}
        for event in events:
            as_of = (utc(event["kickoff_at"]) - timedelta(microseconds=1)).isoformat()
            sides = self.fixture(event["teams"], event["kickoff_at"], as_of)["sides"].values()
            counts["targets"] += 1
            counts["two_calendars"] += all(side["status"] == "OBSERVED_PROVIDER_COVERAGE" for side in sides)
            counts["two_load_histories"] += all(side.get("matched_summaries_14d") for side in sides)
            counts["two_minute_histories"] += all(side.get("provider_minutes_14d") or side.get("nominal_minutes_14d") for side in sides)
            counts["two_venue_histories"] += all(side.get("last_observed_venue") for side in sides)
        return counts
