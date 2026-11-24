"""Create a timestamped research record from existing prematch and historical evidence."""

import argparse
import datetime as dt
import json
from pathlib import Path

from ex_auto_control import auto_control, snapshot
from ex_cross_verify import norm
from ex_decision import MARKETS, assess_market_value, assess_markets
from ex_engine import distribution
from ex_fixture_odds import check_fixture
from ex_history_archive import HistoryArchive, atomic_write, paced_download, source_error, utc
from ex_history_environment import coordinates
from ex_pregame_weather import forecast
from ex_history_sources import ESPN, teams
from run_ex_prematch_archive import summary
from run_ucl_baselines import FIXTURE_CONFIG, calculate_baselines, verified_bytes
from run_ucl_matchday_inputs import TEAM_NEWS, market_quotes, observed_load, parse_team_news
from run_ucl_model_integration import MARKET_FIELDS, score_grid_marginals
from run_ucl_research import UEFA_SNAPSHOT, uefa_fixtures


def record_predictions(manifest, archive, historical, day, clock, provider_history=None, weather_archive=None, uefa_archive=None):
    now = clock()
    config = json.loads(FIXTURE_CONFIG.read_text())
    meta = json.loads(UEFA_SNAPSHOT.with_suffix(".json").read_text())
    if utc(meta["retrieved_at"]) >= now:
        raise ValueError("UEFA evidence not available at analysis time")
    uefa = verified_bytes(UEFA_SNAPSHOT.with_suffix(".html"), meta["sha256"])
    official = set(uefa_fixtures(uefa, 5))
    news_path = historical / "matchday_inputs" / "report.json"
    news, news_source = {}, None
    if news_path.exists():
        candidate = json.loads(news_path.read_text()).get("uefa_preview_source")
        if candidate and Path(candidate["file"]).name == candidate["file"] and utc(candidate["retrieved_at"]) < now:
            news = parse_team_news(verified_bytes(news_path.parent / candidate["file"], candidate["sha256"]))
            news_source = candidate
    if not news and uefa_archive:
        cached = uefa_archive.prior_capture(TEAM_NEWS, now)
        if cached:
            news = parse_team_news(cached[0])
            news_source = cached[2]
    board_source = manifest["board"]
    board_raw, board_at = archive._load(board_source, board_source["url"])
    board = {event["id"]: event for event in json.loads(board_raw)["events"]}
    if len(manifest["records"]) != len({entry["event_id"] for entry in manifest["records"]}):
        raise ValueError("Duplicate prematch record")
    _, _, baselines = calculate_baselines(historical, config)
    fixtures = { (utc(row["fixture"]["kickoff_at"]), norm(row["fixture"]["home"]), norm(row["fixture"]["away"])): row
                 for row in baselines if row["fixture"]["date"] == day }
    aliases = {norm(alias): norm(team) for league in config["domestic_team_names"].values()
               for team, variants in league.items() for alias in (team, *variants)}
    weather, weather_errors = {}, []
    if weather_archive:
        venues = json.loads(Path("config/ex_history_venues.json").read_text())
        venues.update(json.loads(Path("config/ex_pregame_venues.json").read_text()))
        for entry in manifest["records"]:
            match, = board[entry["event_id"]]["competitions"]
            point = coordinates(match.get("venue"), venues)
            if point and now < utc(entry["kickoff_at"]):
                try:
                    observation = forecast(weather_archive, point, entry["kickoff_at"], lambda: clock().isoformat())
                    weather[entry["event_id"]] = {**observation, "venue_source": venues[match["venue"]["id"]]["source"]}
                except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
                    weather_errors.append({"event_id": entry["event_id"], **source_error("forecast", None, exc)})
    now = clock()
    decisions = assess_markets({}, as_of=now.isoformat())
    results = []
    for entry in manifest["records"]:
        event = board[entry["event_id"]]
        match, = event["competitions"]
        kickoff = utc(entry["kickoff_at"])
        names = {side["homeAway"]: side["team"]["displayName"] for side in match["competitors"]}
        if (board_source["url"] != f"{ESPN}/uefa.champions/scoreboard?dates={kickoff:%Y%m%d}"
                or entry["source"]["url"] != f"{ESPN}/uefa.champions/summary?event={entry['event_id']}"
                or utc(match["date"]) != kickoff or match["id"] != entry["event_id"]
                or event["status"]["type"]["state"] != "pre" or teams(match) != entry["teams"]):
            raise ValueError("Prematch board source or identity mismatch")
        raw, captured = archive._load(entry["source"], entry["source"]["url"])
        observed = summary(raw, captured, entry["event_id"], kickoff, entry["teams"])
        if not max(board_at, captured) < now < kickoff:
            raise ValueError("Research snapshot outside pregame window")
        key = kickoff, aliases[norm(names["home"])], aliases[norm(names["away"])]
        if key not in official:
            raise ValueError("UEFA fixture corroboration missing")
        reference = fixtures[key]
        fixture = reference["fixture"]
        baseline = reference["baseline"]
        scores = distribution(baseline["lambda_home"], baseline["lambda_away"])
        marginals = score_grid_marginals(scores["lambda_home"], scores["lambda_away"])
        consistent = (snapshot(scores) == snapshot(baseline)
                      and max(abs(scores[field] - value) for field, value in marginals.items()) < 1e-9)
        lock = check_fixture({**fixture, "fixture_source": board_source["url"],
                              "fixture_checked_at": board_source["retrieved_at"]}, now.isoformat())
        quotes = market_quotes(match.get("odds"), board_source, entry["kickoff_at"])
        percentages = {market: round(100 * scores[field], 2) for market, field in MARKET_FIELDS.items()}
        markets = {}
        for market in MARKETS:
            candidates = [quote for quote in quotes if quote["market"] == market]
            evidence = decisions["markets"][market]
            value = assess_market_value(market, evidence["ex_g"],
                                        candidates[0] if len(candidates) == 1 else None, now.isoformat())
            control = auto_control({"fixture": fixture, "status": "BASELINE_ONLY", "fixture_lock": lock,
                                    "odds_lock": value["odds_lock"], "recompute_consistent": consistent,
                                    "market_baselines_pct": percentages})
            markets[market] = {"research_probability": scores[MARKET_FIELDS[market]],
                               "evidence": evidence, **value, "auto_control": control}
        preview = news.get(key[1:])
        archived_load = provider_history.fixture(entry["teams"], entry["kickoff_at"], now.isoformat()) if provider_history else None
        results.append({"fixture": fixture, "teams": entry["teams"], "sources": [board_source, entry["source"]],
                        "venue": match.get("venue"), "neutral_site": match.get("neutralSite"),
                        "weather_forecast": weather.get(entry["event_id"]),
                        "team_news": preview, "summary_fields": observed, "provider_history": archived_load,
                        "component_status": {
                            "team_strength": "RESEARCH_BASELINE_ONLY",
                            "match_conditions": "OBSERVED_WORKLOAD_AND_AVAILABILITY_SCORE_UNVALIDATED",
                            "external_factors": "VENUE_OBSERVED_MATCHDAY_EFFECTS_UNVERIFIED",
                        },
                        "observed_load": observed_load(json.loads(raw), set(entry["teams"].values()), captured, kickoff),
                        "tur2_consistent": consistent, "score_distribution": scores, "markets": markets,
                        "pup_allowed": decisions["pup_allowed"], "ex_final_allowed": False})
    if len(results) != len(fixtures) or not results or any(not r["tur2_consistent"] for r in results):
        raise ValueError("Incomplete fixture coverage or inconsistent research recomputation")
    if clock() >= min(utc(row["fixture"]["kickoff_at"]) for row in results):
        raise ValueError("Research calculation finished after kickoff")
    return {"analysis_at": now.isoformat(), "kind": "UNCALIBRATED_PREMATCH_RESEARCH",
            "uefa_fixture_source": meta, "uefa_news_source": news_source, "fixtures": results,
            "weather_errors": weather_errors,
            "pup_allowed": False, "ex_final_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--historical", type=Path, required=True)
    parser.add_argument("--history-plan", type=Path)
    parser.add_argument("--history-parts", type=Path)
    parser.add_argument("--weather-cache", type=Path)
    parser.add_argument("--uefa-cache", type=Path)
    parser.add_argument("--day", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if bool(args.history_plan) != bool(args.history_parts):
        parser.error("Provide both history plan and parts")
    provider_history = None
    if args.history_plan:
        from run_ex_history_merge import load_provider_history
        provider_history = load_provider_history(args.history_plan, args.history_parts)
    weather_archive = (HistoryArchive(args.weather_cache, 25, fetch=paced_download(.75))
                       if args.weather_cache else None)
    uefa_archive = HistoryArchive(args.uefa_cache, 0) if args.uefa_cache else None
    report = record_predictions(json.loads(args.manifest.read_text()), HistoryArchive(args.archive, 0),
                                args.historical, args.day, lambda: dt.datetime.now(dt.timezone.utc), provider_history, weather_archive, uefa_archive)
    atomic_write(args.output, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"analysis_at": report["analysis_at"], "fixtures": len(report["fixtures"]),
                      "markets": sum(len(row["markets"]) for row in report["fixtures"]),
                      "news": sum(bool(row["team_news"]) for row in report["fixtures"]),
                      "weather": sum(bool(row["weather_forecast"]) for row in report["fixtures"]),
                      "weather_errors": report["weather_errors"],
                      "verified_quotes": sum(m["odds_lock"]["status"] == "VERIFIED_INPUT"
                                             for row in report["fixtures"] for m in row["markets"].values()),
                      "sides_with_minutes": sum(bool(side.get("nominal_minutes_14d") or side.get("provider_minutes_14d"))
                                                for row in report["fixtures"]
                                                for side in (row["provider_history"] or {}).get("sides", {}).values()),
                      "ex_final_allowed": False}))


if __name__ == "__main__":
    main()
