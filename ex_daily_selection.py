"""Apply daily research-list capacities independently of production decisions."""

import datetime as dt
import math

from ex_decision import MARKETS
from ex_fixture_odds import check_fixture
from ex_performance_v1 import CANDIDATE, KEYS, REFERENCE
from ex_pup_gate import execute_pup


def research_probability(row, market):
    baseline = (row.get("domestic_research") or {}).get("baseline") or {}
    venue = row.get("venue5_research") or {}
    return baseline.get(KEYS[market], venue.get(market))


def daily_selection(rows, verified_ids, *, pup_requested=False):
    count = len(verified_ids)
    dense = count >= 30
    market_limit, combined_limit, evidence_limit = (5, 10, 5) if dense else (3, 6, 3)
    ranked = {market: [] for market in MARKETS}
    combined, evidence, pup = [], [], []
    seen = set()
    for row in rows:
        fixture = row["fixture"]
        event = fixture["event_id"]
        if (event in seen or event not in verified_ids
                or check_fixture(fixture, row["as_of"])["status"] != "VERIFIED_INPUT"):
            continue
        seen.add(event)
        score = (row.get("domestic_research") or {}).get("baseline")
        values = row["market_values"]
        if pup_requested:
            decision = execute_pup(row["markets"]["markets"], MARKETS, values, score, requested=True)
            pup.append({"event_id": event, **decision})
        if row["tur2"] is not True:
            continue
        signals = {}
        verified_prices = []
        for market in MARKETS:
            probability = research_probability(row, market)
            price = values[market]["odds_lock"]
            if (type(probability) not in (float, int) or not math.isfinite(probability)
                    or not 0 <= probability <= 1 or price.get("decision") == "PASS_ODDS_1_19_OR_LOWER"):
                continue
            candidate = row.get("performance_v1", {}).get(CANDIDATE, {}).get(KEYS[market])
            signal = {"event_id": event, "market": market, REFERENCE: probability, CANDIDATE: candidate,
                      "verified_price": price["status"] == "VERIFIED_INPUT"}
            ranked[market].append(signal)
            signals[market] = signal
            if signal["verified_price"]:
                verified_prices.append(market)
        if not signals:
            continue
        entry = {"event_id": event, "fixture": fixture, "markets": signals}
        combined.append(entry)
        if row["fixture_evidence"]["status"] == "FIXTURE_CROSS_VERIFIED" and verified_prices:
            components = row.get("component_research", {})
            evidence.append({**entry, "verified_price_markets": verified_prices,
                             "available_components": sum(part.get("score") is not None
                                 for market in verified_prices
                                 for part in components.get(market, {}).get("components", {}).values())})
    for rows_for_market in ranked.values():
        rows_for_market.sort(key=lambda row: (-row[REFERENCE], row["event_id"]))
    combined.sort(key=lambda row: (-max(p[REFERENCE] for p in row["markets"].values()), row["event_id"]))
    evidence.sort(key=lambda row: (-row["available_components"], -len(row["verified_price_markets"]),
                                  row["event_id"]))
    # These are match research lists. Selecting a live market remains PUP's responsibility.
    return {"mode": "YOĞUN" if dense else "NORMAL", "verified_fixture_count": count,
            "limits": {"per_market": market_limit, "combined": combined_limit, "evidence": evidence_limit},
            "markets": {market: items[:market_limit] for market, items in ranked.items()},
            "combined": combined[:combined_limit], "evidence": evidence[:evidence_limit],
            "pup": pup, "production_allowed": False, "ex_final_allowed": False}


def verified_fixture_ids(manifest, cache, cutoff):
    """Verify day, league, identity and kickoff against each raw fixture board."""
    from ex_espn_provider import ESPN_LEAGUES
    from ex_history_sources import ESPN
    from run_ex_prematch_archive import prematch_fixtures

    day = dt.date.fromisoformat(manifest["day"])
    seen, conflicts = {}, set()
    for league, report in manifest["reports"].items():
        slug = ESPN_LEAGUES[league]
        url = f"{ESPN}/{slug}/scoreboard?dates={day:%Y%m%d}"
        try:
            raw, captured = cache._load(report["board"], url)
            fixtures = prematch_fixtures(raw, captured, day, slug, dt.timedelta(hours=48))
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
        for event, kickoff, teams in fixtures:
            if not captured < cutoff < kickoff:
                continue
            identity = league, kickoff, teams
            if seen.setdefault(event, identity) != identity:
                conflicts.add(event)
    return seen.keys() - conflicts
