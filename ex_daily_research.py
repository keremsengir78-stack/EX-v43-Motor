"""Keep date-granular domestic UCL baselines outside the frozen holdout ledger."""

from datetime import datetime, timedelta, timezone
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from ex_auto_control import auto_control
from ex_cross_verify import norm
from ex_decision import MARKETS, assess_market_value, assess_markets
from ex_research_components import score_components, weather_vector
from ex_fixture_odds import check_fixture, check_odds
from ex_history_archive import utc
from ex_engine import weighted_form
from ex_team_identity import team_identities
from ex_leagues import APPROVED_LEAGUES, CUP_HISTORY_SLUGS, UEFA_CUPS, season_bounds
from ex_ucl_baseline import cross_league_baseline
from run_ucl_baselines import CUTOFF, FIXTURE_CONFIG, captured_rows, select_rows, team_index, verified_bytes
from run_ucl_research import UEFA_SNAPSHOT, uefa_fixtures

MARKET_KEYS = {"2.5_UST": "over25", "KG_VAR": "btts", "MS1": "home_win",
               "MSX": "draw", "MS2": "away_win"}


def domestic_snapshot(root):
    config = json.loads(FIXTURE_CONFIG.read_text())
    leagues, aliases = team_index(config["domestic_team_names"])
    names = {}
    for (_, alias), name in aliases.items():
        if names.setdefault(alias, name) != name:
            raise ValueError(f"Ambiguous domestic team alias: {alias}")
    rows, coverage = select_rows(captured_rows(root), aliases)
    fixtures = {(utc(row["kickoff_at"]), row["home"], row["away"]) for row in config["fixtures"]}
    return rows, coverage, names, leagues, fixtures


DOMESTIC_BY_SLUG = {data[1]: league for league, data in APPROVED_LEAGUES.items() if league not in UEFA_CUPS}


def rolling_domestic(fixture, by_team, as_of, *, retrospective=False, archive_leagues=None, diagnostics=None):
    """Join current domestic membership by ESPN club ID; never infer from a name."""
    catalog = DOMESTIC_BY_SLUG | (archive_leagues or {}) if retrospective else DOMESTIC_BY_SLUG
    if fixture["league"] in UEFA_CUPS - {"UCL"}:
        catalog = catalog | {slug: league for league, slug in CUP_HISTORY_SLUGS.items()}
    cutoff = as_of.date()
    rows, leagues = [], []
    ambiguous = False
    for side in ("home", "away"):
        club = fixture["team_ids"][side]
        history = [row for row in by_team.get(club, ())
                   if row["competition"] in catalog and row["kickoff"].date() < cutoff
                   and row["finished"] is not None and row["score"] is not None
                   and (row["finished"] < as_of if retrospective
                        else row["finished"] <= row["captured_at"] < as_of)]
        current = {row["competition"] for row in history
                   if row["kickoff"].date() >= season_bounds(catalog[row["competition"]], cutoff)[0]}
        if fixture["league"] not in UEFA_CUPS:
            current.intersection_update({APPROVED_LEAGUES[fixture["league"]][1]})
        diagnostic = {"team_id": club, "eligible_rows": len(history),
                      "current_competitions": sorted(current),
                      "archived_competitions": sorted({row["competition"] for row in history})}
        if diagnostics is not None:
            diagnostics[side] = diagnostic
        if len(current) != 1:
            diagnostic["reason"] = "NO_CURRENT_DOMESTIC_RECORDS" if not current else "AMBIGUOUS_DOMESTIC_LEAGUE"
            ambiguous = True
            continue
        competition, = current
        league = catalog[competition]
        leagues.append(league)
        club_rows = [{"date": row["kickoff"].date(), "league": league,
                      "home": row["teams"]["home"], "away": row["teams"]["away"],
                      "hg": row["score"][0], "ag": row["score"][1]} for row in history
                     if row["competition"] == competition]
        rows.extend(club_rows)
        if diagnostics is not None:
            current_start, previous_start = season_bounds(league, cutoff)
            unique_rows = {(r["date"], r["home"], r["away"]): r for r in club_rows}
            _, audit = weighted_form(sorted(unique_rows.values(), key=lambda r: r["date"]),
                                     club, side, cutoff, league, current_start, previous_start)
            names = ("venue_last5", "venue_last10", "current_season", "previous_season_venue")
            counts = dict(zip(names, audit["counts"], strict=True))
            diagnostic.update(league=league, current_season_start=current_start.isoformat(),
                              previous_season_start=previous_start.isoformat(), sample_counts=counts,
                              missing_samples=[name for name, minimum in zip(names, (5, 10, 1, 1), strict=True)
                                               if counts[name] < minimum])
    if ambiguous:
        return None
    unique = {(r["league"], r["date"], r["home"], r["away"]): r for r in rows}
    first, prior = season_bounds(fixture["league"], cutoff)
    return sorted(unique.values(), key=lambda row: row["date"]), fixture, *leagues, fixture["team_ids"]["home"], fixture["team_ids"]["away"], first.isoformat(), prior.isoformat()


@lru_cache(maxsize=1)
def official_ucl_index():
    config = json.loads(FIXTURE_CONFIG.read_text())
    metadata = json.loads(UEFA_SNAPSHOT.with_suffix(".json").read_text())
    if metadata["url"] != config["source"]:
        raise ValueError("Unexpected official UCL evidence source")
    raw = verified_bytes(UEFA_SNAPSHOT.with_suffix(".html"), metadata["sha256"])
    _, aliases = team_index(config["domestic_team_names"])
    canonical = {alias: name for (_, alias), name in aliases.items()}
    indexed = {(stamp, canonical.get(home, home), canonical.get(away, away))
               for stamp, home, away in uefa_fixtures(raw, config["matchday"])}
    return metadata, canonical, indexed


@lru_cache(maxsize=1)
def reviewed_fixture_calendars():
    path = Path(__file__).with_name("config") / "ex_reviewed_fixture_calendars.json"
    return json.loads(path.read_text(encoding="utf-8"))


def reviewed_fixture_source(fixture, board, as_of):
    """Join a source-owned calendar review to the exact provider-board identity."""
    review = reviewed_fixture_calendars().get(fixture["date"], {}).get(fixture["league"])
    if not review:
        return None
    url = urlsplit(review["url"])
    reviewed = utc(review["reviewed_at"])
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or not re.fullmatch(r"[0-9a-f]{64}", board.get("sha256", ""))
            or url.hostname == urlsplit(board["url"]).hostname
            or not reviewed < as_of < utc(fixture["kickoff_at"])):
        return None
    wall_time = datetime.fromisoformat(f"{fixture['date']}T{review['official_local_time']}")
    offset = timezone(timedelta(hours=review["official_utc_offset_hours"]))
    if wall_time.replace(tzinfo=offset) != utc(fixture["kickoff_at"]):
        return None
    keys = ("event_id", "team_ids", "home", "away", "kickoff_at")
    if sum(all(fixture.get(key) == match[key] for key in keys) for match in review["fixtures"]) != 1:
        return None
    return {"url": review["url"], "reviewed_at": review["reviewed_at"],
            "kind": "REVIEWED_OFFICIAL_FIXTURE_CALENDAR"}


def corroborated_fixture(fixture, board, as_of, cup_evidence=None):
    result = {"status": "UNVERIFIED", "scope": "FIXTURE_IDENTITY_ONLY", "sources": []}
    if not board:
        return result
    status = check_fixture(fixture, as_of.isoformat())
    if (status["status"] != "VERIFIED_INPUT" or board["url"] != fixture["fixture_source"]
            or utc(board["retrieved_at"]) != utc(fixture["fixture_checked_at"])):
        return result
    if fixture["league"] not in UEFA_CUPS and cup_evidence is None:
        reviewed = reviewed_fixture_source(fixture, board, as_of)
        if reviewed:
            result.update(status="FIXTURE_CROSS_VERIFIED", sources=[board, reviewed])
        return result
    if fixture["league"] != "UCL" and cup_evidence is None:
        return result
    if cup_evidence:
        index, metadata = cup_evidence
        aliases = {}
    else:
        metadata, aliases, index = official_ucl_index()
    home, away = (aliases.get(norm(fixture[side]), norm(fixture[side])) for side in ("home", "away"))
    kickoff = utc(fixture["kickoff_at"])
    ids = fixture.get("team_ids") or {}
    reviews = set()
    if cup_evidence:
        mapped = []
        registry = team_identities()
        for side, name in (("home", home), ("away", away)):
            record = registry.get(ids.get(side))
            claimants = {club for club, entry in registry.items()
                         if entry["observed"] < as_of and name == norm(entry["espn_name"])}
            if claimants and ids.get(side) not in claimants:
                return result
            if record and record["observed"] < as_of:
                if name != norm(record["espn_name"]):
                    return result
                if name != record["uefa_alias"]:
                    reviews.add(record["review"])
                name = record["uefa_alias"]
            mapped.append(name)
        if (kickoff, *mapped) in index:
            home, away = mapped
        else:
            reviews.clear()
    if utc(metadata["retrieved_at"]) < as_of < kickoff and (kickoff, home, away) in index:
        result.update(status="FIXTURE_CROSS_VERIFIED", sources=[board, metadata])
        if reviews:
            result["identity_reviews"] = sorted(reviews)
    return result



def recent_domestic_scores(fixture, snapshot, as_of):
    """Expose date-granular observations without feeding them to the timed workload model."""
    if fixture["league"] != "UCL" or not snapshot:
        return {}
    rows, _, names, leagues, fixtures = snapshot
    home, away = (names.get(norm(fixture[side])) for side in ("home", "away"))
    kickoff = utc(fixture["kickoff_at"])
    if (kickoff, home, away) not in fixtures or as_of < utc(CUTOFF + "T00:00:00Z"):
        return {}
    start = (kickoff - timedelta(days=14)).date()
    return {
        side: [{"date": str(row["date"]), "home": row["home"], "away": row["away"],
                "score": [row["hg"], row["ag"]]}
               for row in rows if row["league"] == leagues[club] and club in (row["home"], row["away"])
               and start < row["date"] < min(as_of.date(), kickoff.date())]
        for side, club in (("home", home), ("away", away))
        if leagues.get(club) in {"az.1", "cz.1", "ua.1"}
    }

def fixture_acceptance(review, fixture, as_of):
    """Bind an upstream acceptance record to this exact, still-upcoming fixture."""
    if not isinstance(review, dict) or not isinstance(review.get("fixture"), dict):
        return None
    scope = review["fixture"]
    if any(not fixture.get(key) or scope.get(key) != fixture[key]
           for key in ("event_id", "league", "team_ids")):
        return None
    try:
        kickoff = utc(fixture["kickoff_at"])
        if utc(scope["kickoff_at"]) == kickoff and utc(review["accepted_at"]) < as_of < kickoff:
            return review
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    return None


def daily_analysis(fixture, window, snapshot, as_of, *, venue_recomputed=False, by_team=None, observations=None, quotes=(), board_evidence=None, component_model=None,
                   strength=None, workload=None, weather=None, cup_evidence=None, ingestion_review=None, context_review=None, component_review=None):
    """Join the two models for display while leaving their evaluation cohorts separate."""
    baseline = None
    recomputed = False
    domestic_diagnostics = {}
    if fixture["league"] in APPROVED_LEAGUES and by_team:
        inputs = rolling_domestic(fixture, by_team, as_of, diagnostics=domestic_diagnostics)
        if inputs:
            kwargs = {"cutoff_date": as_of.date().isoformat()}
            baseline = cross_league_baseline(*inputs, **kwargs)
            recomputed = baseline == cross_league_baseline(*inputs, **kwargs)
            baseline["history_scope"] = "ROLLING_DOMESTIC_PROVIDER_TEAM_ID"
            if fixture["league"] not in UEFA_CUPS and baseline.get("baseline"):
                baseline["status"] = "UNCALIBRATED_SAME_LEAGUE_BASELINE"
    if fixture["league"] == "UCL" and snapshot and not (baseline or {}).get("baseline"):
        rows, _, names, leagues, fixtures = snapshot
        home, away = (names.get(norm(fixture[side])) for side in ("home", "away"))
        kickoff = utc(fixture["kickoff_at"])
        if (kickoff, home, away) in fixtures and utc(CUTOFF + "T00:00:00Z") <= as_of:
            inputs = (rows, fixture, leagues[home], leagues[away], home, away, "2026-07-01", "2025-07-01")
            baseline = cross_league_baseline(*inputs)
            recomputed = baseline == cross_league_baseline(*inputs)
            baseline["history_scope"] = "VERIFIED_MATCHDAY5_DOMESTIC_SNAPSHOT"
    values = baseline.get("baseline") if baseline else None
    if values:
        market_percentages = {market: 100 * values[key] for market, key in MARKET_KEYS.items()}
    elif window is not None:
        market_percentages = {market: 100 * value for market, value in window.items()}
        market_percentages["MSX"] = max(0.0, 100 - market_percentages["MS1"] - market_percentages["MS2"])
        recomputed = venue_recomputed
    else:
        market_percentages = None
    time = as_of.isoformat()
    if strength is None and values:
        strength = {market: values[MARKET_KEYS[market]] for market in MARKETS}
    factors = weather_vector(weather, fixture["kickoff_at"], as_of)
    components, decisions = score_components(strength, workload, factors, component_model, as_of)
    kickoff = utc(fixture["kickoff_at"])
    live_start = kickoff - timedelta(hours=48)
    live_window = live_start <= as_of < kickoff
    if board_evidence:
        live_window = live_window and utc(board_evidence["retrieved_at"]) >= live_start
    summary_source = (observations or {}).get("summary_source")
    if summary_source:
        live_window = live_window and utc(summary_source["retrieved_at"]) >= live_start
    certified = fixture_acceptance(component_review, fixture, as_of) if live_window else None
    if certified and utc(certified["accepted_at"]) < live_start:
        certified = None
    if certified and certified.get("status") == "COMPONENTS_CROSS_VERIFIED":
        certified = certified.get("markets")
    else:
        certified = None
    if isinstance(certified, dict):
        decisions = assess_markets(certified, time, competition=fixture["league"])
    else:
        certified = {}
    values_by_market, selected_quotes = {}, {}
    for market in MARKETS:
        offers = [quote for quote in quotes if quote["market"] == market
                  and check_odds(quote, time)["status"] == "VERIFIED_INPUT"]
        unique = {(q["bookmaker"], q["decimal_odds"]): q for q in offers}
        selected = next(iter(unique.values())) if len(unique) == 1 else None
        selected_quotes[market] = selected
        value = assess_market_value(market, decisions["markets"][market]["ex_g"], selected, time)
        values_by_market[market] = {**value, "observed_quotes": offers}
    evidence = corroborated_fixture(fixture, board_evidence, as_of, cup_evidence)
    ingestion = fixture_acceptance(ingestion_review, fixture, as_of)
    context = fixture_acceptance(context_review, fixture, as_of)
    if not live_window or evidence["status"] != "FIXTURE_CROSS_VERIFIED" or (
            ingestion and utc(ingestion["accepted_at"]) < live_start):
        ingestion = None
    if not live_window or (context and utc(context["accepted_at"]) < live_start):
        context = None
    gate = {"status": "BASELINE_ONLY" if values or window is not None else "INCOMPLETE",
            "fixture_lock": check_fixture(fixture, time),
            "market_baselines_pct": market_percentages,
            "recompute_consistent": recomputed,
            "league": fixture["league"], "as_of": time,
            "full_historical_windows": bool(values),
            "live_evidence_window": live_window, "live_evidence_starts_at": live_start.isoformat()}
    gate_inputs = {"ingestion": ingestion, "context_evidence": context, "fixture_evidence": evidence,
                   "pup_requested": False}
    checks = {market: auto_control({**gate, "market": market, "odds_lock": value["odds_lock"]},
                                   **gate_inputs, market_evidence=certified.get(market),
                                   quote=selected_quotes[market])
              for market, value in values_by_market.items()}
    finals = [market for market, result in checks.items() if result["ex_final_allowed"]]
    return {"fixture": fixture, "as_of": time, "venue5_research": window,
            "domestic_research": baseline, "domestic_diagnostics": domestic_diagnostics, "markets": decisions, "market_values": values_by_market,
            "observed_inputs": {**(observations or {}), "prematch_weather_forecast": weather,
                                "dated_domestic_scores": recent_domestic_scores(fixture, snapshot, as_of)},
            "component_research": components,
            "ex_final_status": "FINAL" if finals else "BLOCKED_PENDING_REQUIRED_EVIDENCE",
            "final_markets": finals,
            "live_evidence_window": live_window, "live_evidence_starts_at": live_start.isoformat(),
            "tur2": recomputed if market_percentages else None, "auto_control": auto_control(gate, **gate_inputs, require_odds=False),
            "auto_control_by_market": checks, "fixture_evidence": evidence,
            "ingestion_acceptance": ingestion, "context_acceptance": context,
            "calibration_cohort": "VENUE5_ONLY" if window else None, "ex_final_allowed": bool(finals)}
