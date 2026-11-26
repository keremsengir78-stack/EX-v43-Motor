"""Capture matchday 5 team news, observed match load and sportsbook quotes."""

import datetime as dt
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ex_cross_verify import norm
from ex_fixture_odds import check_odds
from ex_uefa_provider import parse_team_news
from run_ucl_baselines import FIXTURE_CONFIG
from run_ucl_research import capture_fixture_source, retry_research_request

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions"
TEAM_NEWS = (
    "https://www.uefa.com/uefachampionsleague/news/"
    "02ab-2223c67db015-c4f7874e074e-1000--champions-league-predicted-line-ups-matchday-5-team-news-/"
)


def timestamp(value):
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError("Expected a UTC timestamp")
    return parsed


def market_quotes(odds, metadata, kickoff, *, observed_lines=None):
    def object_at(node, *keys):
        for key in keys:
            node = node.get(key) if isinstance(node, dict) else None
        return node if isinstance(node, dict) else {}

    offers = []
    for quote in odds if isinstance(odds, list) else ():
        provider = object_at(quote, "provider").get("name")
        home = object_at(quote, "moneyline", "home", "close")
        away = object_at(quote, "moneyline", "away", "close")
        over = object_at(quote, "total", "over", "close")
        if observed_lines is not None and isinstance(over.get("line"), str):
            observed_lines.add(over["line"])
        selections = {"MS1": home, "MS2": away}
        if over.get("line") == "o2.5":
            selections["2.5_UST"] = over
        for market, price in selections.items():
            american = price.get("odds")
            if not isinstance(american, str) or not re.fullmatch(r"[+-][0-9]{3,6}", american):
                continue
            signed = int(american)
            if abs(signed) < 100:
                continue
            decimal = 1 + (signed / 100 if signed > 0 else 100 / -signed)
            offer = {
                "market": market, "bookmaker": provider, "american_odds": american,
                "decimal_odds": decimal, "observed_at": metadata["retrieved_at"],
                "source": metadata["url"], "sha256": metadata["sha256"],
            }
            checked = check_odds(offer, kickoff)
            if checked["status"] == "VERIFIED_INPUT":
                offers.append({**offer, "odds_gate": checked["decision"]})
    return offers


def observed_load(summary, team_ids, cutoff, kickoff):
    teams = {}
    for block in summary["lastFiveGames"]:
        team_id = block["team"]["id"]
        if team_id not in team_ids:
            continue
        games = {}
        for game in block["events"]:
            when = timestamp(game["gameDate"])
            if (when >= cutoff or team_id not in (game["homeTeamId"], game["awayTeamId"])
                    or game.get("gameResult") not in {"W", "D", "L"}):
                continue
            games[game["id"]] = {
                "event_id": game["id"], "kickoff_at": game["gameDate"],
                "competition": game["competitionName"],
            }
        recent = sorted(games.values(), key=lambda game: timestamp(game["kickoff_at"]), reverse=True)
        teams[team_id] = {
            "matches_shown": recent,
            "observed_matches_previous_14_days": sum(
                kickoff - timestamp(game["kickoff_at"]) <= dt.timedelta(days=14) for game in recent
            ),
            "hours_since_last_observed_kickoff": round(
                (kickoff - timestamp(recent[0]["kickoff_at"])).total_seconds() / 3600, 2
            ) if recent else None,
        }
    return teams


def main():
    root = Path("ucl_research_output/matchday_inputs")
    root.mkdir(parents=True, exist_ok=True)
    config = json.loads(FIXTURE_CONFIG.read_text())
    aliases = {norm(variant): name for clubs in config["domestic_team_names"].values()
               for name, variants in clubs.items() for variant in [name, *variants]}
    fixtures = {}
    for day in sorted({fixture["date"] for fixture in config["fixtures"]}):
        raw, meta = retry_research_request(
            capture_fixture_source, root, f"scoreboard-{day}", f"{ESPN}/scoreboard?dates={day.replace('-', '')}"
        )
        for event in json.loads(raw)["events"]:
            competition, = event["competitions"]
            sides = {item["homeAway"]: item["team"] for item in competition["competitors"]}
            key = aliases[norm(sides["home"]["displayName"])], aliases[norm(sides["away"]["displayName"])]
            if key in fixtures:
                raise ValueError("Duplicate ESPN scoreboard fixture")
            fixtures[key] = event, competition, sides, meta
    news_raw, news_meta = retry_research_request(capture_fixture_source, root, "uefa-team-news", TEAM_NEWS)
    news = parse_team_news(news_raw)

    def collect(fixture):
        result = {"fixture": fixture, "ex_g": None, "ex_d": None, "ex_final_allowed": False, "decision": "NO_FINAL"}
        event, competition, sides, meta = fixtures[fixture["home"], fixture["away"]]
        kickoff = timestamp(fixture["kickoff_at"])
        if timestamp(event["date"]) != kickoff:
            raise ValueError("ESPN kickoff differs from fixture manifest")
        if timestamp(meta["retrieved_at"]) >= kickoff or event["status"]["type"]["state"] != "pre":
            return {**result, "status": "PREMATCH_CAPTURE_UNAVAILABLE"}
        preview = news.get((norm(fixture["home"]), norm(fixture["away"])))
        if preview and timestamp(news_meta["retrieved_at"]) < kickoff:
            result["uefa_preview"] = preview
        result["market_quotes"] = market_quotes(competition.get("odds", []), meta, fixture["kickoff_at"])
        observed_markets = {quote["market"] for quote in result["market_quotes"]}
        result["missing_market_quotes"] = [
            market for market in ("2.5_UST", "KG_VAR", "MS1", "MS2") if market not in observed_markets
        ]
        result["scoreboard_source"] = meta
        result["venue"] = competition.get("venue")
        try:
            raw, summary_meta = retry_research_request(
                capture_fixture_source, root, f"summary-{event['id']}", f"{ESPN}/summary?event={event['id']}"
            )
            summary = json.loads(raw)
            header = summary["header"]
            match, = header["competitions"]
            team_ids = {side: item["id"] for side, item in sides.items()}
            if (header["id"] != event["id"] or timestamp(match["date"]) != kickoff
                    or {team["homeAway"]: team["id"] for team in match["competitors"]} != team_ids
                    or match["status"]["type"]["state"] != "pre"
                    or timestamp(summary_meta["retrieved_at"]) >= kickoff):
                raise ValueError("Summary identity or prematch cutoff failed")
            load = observed_load(summary, set(team_ids.values()), timestamp(summary_meta["retrieved_at"]), kickoff)
            result["observed_match_load"] = {side: load.get(team_id) for side, team_id in team_ids.items()}
            result["neutral_site"] = match.get("neutralSite")
            result["summary_source"] = summary_meta
        except (OSError, ValueError, KeyError, TypeError) as exc:
            result["summary_error"] = str(exc)
        return result

    with ThreadPoolExecutor(max_workers=5) as pool:
        records = list(pool.map(collect, config["fixtures"]))
    report = {
        "uefa_preview_source": news_meta, "fixtures": records, "ex_final_allowed": False,
        "notes": [
            "UEFA lineups are predicted. Rotation and fatigue impact are not assigned scores.",
            "Recent match counts are lower bounds from displayed completed games.",
            "Quote capture time is the observation time, not the bookmaker's last update.",
        ],
    }
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
