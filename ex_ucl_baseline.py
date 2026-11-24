"""Cross-league research baseline; not calibrated EX-G."""
from ex_engine import weighted_form, distribution, date

def cross_league_baseline(rows,fixture,home_league,away_league,home_name,away_name,season_start,previous_start, *, cutoff_date="2026-11-24"):
    cutoff=date(cutoff_date)
    ss,ps=date(season_start),date(previous_start)
    def bounds(league):
        return (date("2026-01-01"),date("2025-01-01")) if league=="no.1" else (ss,ps)
    home,ha=weighted_form(rows,home_name,"home",cutoff,home_league,*bounds(home_league))
    away,aa=weighted_form(rows,away_name,"away",cutoff,away_league,*bounds(away_league))
    result = {
        "fixture": fixture,
        "samples": {"home": ha, "away": aa},
        "domestic_leagues": {"home": home_league, "away": away_league},
        "cross_league_strength_adjusted": False,
        "calibrated": False,
        "ex_final_allowed": False,
        "status": "BLOCKED",
    }
    if home is None or away is None or any(x["counts"][0]!=5 or x["counts"][1]!=10 for x in (ha,aa)):
        result["missing"] = ["complete_domestic_venue_samples"]
        return result
    lh=max(.05,min(5,(home[0]+away[1])/2))
    la=max(.05,min(5,(away[0]+home[1])/2))
    result.update(status="UNCALIBRATED_CROSS_LEAGUE_BASELINE",baseline=distribution(lh,la))
    return result
