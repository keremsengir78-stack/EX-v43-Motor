"""Date-only, odds-free historical inputs shared by domestic and UCL fixtures."""

from bisect import bisect_left
from collections import defaultdict
from datetime import timedelta
from statistics import mean

from ex_decision import MARKETS


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
