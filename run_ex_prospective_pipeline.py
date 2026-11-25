"""Create and settle a prospective research ledger using immutable archive inputs."""

import argparse
import datetime as dt
import json
from pathlib import Path
from statistics import mean
from urllib.parse import urlsplit

from ex_daily_official import BELGIUM_CALENDAR, belgian_links, belgian_match_hint, league_reviews
from ex_daily_research import daily_analysis, domestic_snapshot
from ex_decision import MARKETS, WEIGHTS, weighted_evidence
from ex_espn_provider import ESPN_LEAGUES
from ex_historical_features import market_labels
from ex_history_archive import BudgetExhausted, HistoryArchive, atomic_write, paced_download, source_error, utc
from ex_history_sources import ESPN, match_detail, teams, validated_team_minutes
from ex_model_challengers import compare_calibration
from ex_official_calendar import calendar_fixtures
from run_ex_official_sources import ALTERNATE_CALENDARS, checked, read_evidence
from ex_rolling_scoreboards import scoreboard_facts
from ex_retrospective import observed_season, settled_facts, window, workload
from run_ex_prematch_archive import prematch_fixtures, summary
from run_ucl_matchday_inputs import market_quotes, observed_load
from run_ex_prospective_validation import evaluate, join_holdout, read_rows
from run_ex_retrospective import load_facts


def jsonl(rows):
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode()


def portable_facts(path):
    """Restore normalized facts emitted by the hash-verifying raw replay."""
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if not rows or len({r["event_id"] for r in rows}) != len(rows):
        raise ValueError("Empty or duplicate historical facts")
    for row in rows:
        for field in ("kickoff", "captured_at", "finished"):
            if row[field] is not None:
                row[field] = utc(row[field])
        if row["score"] is not None:
            row["score"] = tuple(row["score"])
    return rows


def forecast_rows(manifest, cache, facts, now, *, daily=None, domestic=None, component_model=None, weather=None):
    available = [fact for fact in facts if fact["score"] is not None and fact["finished"]
                 and fact["finished"] <= fact["captured_at"] < now]
    labels = {row["event_id"]: market_labels(*row["score"]) for row in available}
    by_team, domestic_teams = {}, {}
    for row in available:
        for club in row["teams"].values():
            domestic_teams.setdefault(club, []).append(row)
            if row.get("evidence_scope") != "ESPN_SCOREBOARD_RESEARCH":
                by_team.setdefault(club, []).append(row)
    rows, skipped = [], []
    belgian = archived_belgian_links(manifest, cache, now)
    for league, report in manifest["reports"].items():
        competition = ESPN_LEAGUES[league]
        board_source = report["board"]
        board_raw, board_at = cache._load(board_source, board_source["url"])
        if board_source["url"] != f"{ESPN}/{competition}/scoreboard?dates={manifest['day'].replace('-', '')}":
            raise ValueError("Board URL does not match registered competition and day")
        events = {event["id"]: event for event in json.loads(board_raw)["events"]}
        for fixture in report["records"]:
            event_id = fixture["event_id"]
            event = events[event_id]
            kickoff = utc(fixture["kickoff_at"])
            (match,) = event["competitions"]
            if (match["id"] != event_id or utc(match["date"]) != kickoff
                    or teams(match) != fixture["teams"] or event["status"]["type"]["state"] != "pre"):
                raise ValueError("Board does not corroborate fixture")
            source = fixture["source"]
            if source["url"] != f"{ESPN}/{competition}/summary?event={event_id}":
                raise ValueError("Summary URL does not match fixture")
            raw, captured = cache._load(source, source["url"])
            observed = summary(raw, captured, event_id, kickoff, fixture["teams"])
            season, season_basis = observed_season(competition, kickoff, event.get("season", {}).get("year"))
            if not max(captured, board_at) < now < kickoff or type(season) is not int:
                skipped.append({"event_id": event_id, "reason": "TIME_OR_SEASON_UNAVAILABLE"})
                continue
            teams_features = []
            for side in ("home", "away"):
                club = fixture["teams"][side]
                history = [{**row, "index_team": club} for row in by_team.get(club, ()) if row["event_id"] != event_id]
                league_rows = [(row["kickoff"], "home" if row["teams"]["home"] == club else "away", row)
                               for row in history if row["competition"] == competition]
                short, strength = window(sorted(league_rows, key=lambda row: row[0]), labels, side, season)
                context, minutes = workload(history, kickoff)
                teams_features.append((short, strength, context, minutes))
            home, away = teams_features
            players = {side["homeAway"]: side["team"]["displayName"] for side in match["competitors"]}
            short = {m: mean((home[0][m], away[0][m])) for m in MARKETS} if home[0] and away[0] else None
            strength = ({m: mean((home[1][m], away[1][m])) for m in MARKETS}
                        if home[1] and away[1] else None)
            if daily is not None:
                # Rebuild the venue windows from source rows when auditing this path.
                replay = []
                if short is not None:
                    for side in ("home", "away"):
                        club = fixture["teams"][side]
                        samples = [(r["kickoff"], "home" if r["teams"]["home"] == club else "away", r)
                                   for r in by_team.get(club, ()) if r["competition"] == competition
                                   and r["event_id"] != event_id]
                        replay.append(window(sorted(samples, key=lambda r: r[0]), labels, side, season)[0])
                consistent = bool(replay) and all(short[m] == mean((replay[0][m], replay[1][m])) for m in MARKETS)
                identity = {"event_id": event_id, "date": kickoff.date().isoformat(), "league": league,
                            "kickoff_at": kickoff.isoformat(), **players, "team_ids": fixture["teams"],
                            "season": season, "season_basis": season_basis,
                            "fixture_source": board_source["url"], "fixture_checked_at": board_at.isoformat()}
                payload = json.loads(raw)
                workload_issue = None
                try:
                    source_load = observed_load({"lastFiveGames": payload.get("lastFiveGames") or []},
                                                fixture["teams"].values(), now, kickoff)
                except (ValueError, KeyError, TypeError, AttributeError) as exc:
                    source_load = {}
                    workload_issue = source_error("optional_recent_schedule", source["url"], exc)
                side_load = {}
                for side, feature in zip(("home", "away"), teams_features, strict=True):
                    context, minutes = feature[2:]
                    side_load[side] = {
                        "completed_match_count_14d_archived": round(context[1] * 5) if context else None,
                        "rest_hours_since_archived_full_time_capped_at_336": round(context[0] * 336, 2) if context else None,
                        "validated_minutes_proxy_available": minutes is not None,
                        "source_recent_schedule": source_load.get(fixture["teams"][side]),
                    }
                game_info = payload.get("gameInfo") or {}
                observations = {**observed, "workload": side_load, "summary_source": source,
                                "provider_weather_observed": bool(game_info.get("weather")),
                                "confirmed_lineup_required": False, "individual_international_break_required": False,
                                "recent_schedule_issue": workload_issue}
                quotes = market_quotes(match.get("odds") or event.get("odds"), board_source, kickoff.isoformat())
                daily.append(daily_analysis(identity, short, domestic, now, venue_recomputed=consistent,
                                            by_team=domestic_teams, observations=observations, quotes=quotes,
                                            board_evidence=board_source, component_model=component_model,
                                            strength=strength, workload=(*home[2], *away[2]) if home[2] and away[2] else None,
                                            weather=(weather or {}).get(event_id)))
            if short is None:
                skipped.append({"event_id": event_id, "league": league, "teams": fixture["teams"],
                                "missing_venue5": [s for s, feature in zip(("home", "away"), teams_features, strict=True)
                                                   if feature[0] is None], "reason": "VENUE5_HISTORY_INCOMPLETE"})
                continue
            rows.append({"event_id": event_id, "kickoff": kickoff.isoformat(), "forecast_at": now.isoformat(),
                         "league": league, "season": season, "season_basis": season_basis, "teams": fixture["teams"], "names": players,
                         **({"official_match_url": belgian_match_hint(belgian, kickoff, players)} if league == "be.1" else {}),
                         "short": short,
                         "strength": strength,
                         "observed_context": {"home": home[2], "away": away[2],
                                              "home_minutes": home[3], "away_minutes": away[3]},
                         "source": source, "kind": "PROSPECTIVE_VENUE5_RESEARCH"})
    return rows, skipped


def bind_espn_context(context, reports, cache_root, day):
    """Attach archived data only after a unique league, kickoff and home-away match."""
    archive = HistoryArchive(cache_root, 0)
    for league, official in context.items():
        registered = reports.get(league)
        if not official or not registered:
            continue
        competition = ESPN_LEAGUES[league]
        board = registered["board"]
        expected = f"{ESPN}/{competition}/scoreboard?dates={day:%Y%m%d}"
        raw, captured = archive._load(board, expected)
        valid = {event_id: (kickoff, sides) for event_id, kickoff, sides in
                 prematch_fixtures(raw, captured, day, competition, dt.timedelta(hours=48))}
        records = {row["event_id"]: row for row in registered["records"]}
        items = json.loads(raw)["events"]
        for fixture in official:
            if not fixture["competition_verified"]:
                continue
            candidates = []
            for item in items:
                event_id = item["id"]
                if event_id not in records or event_id not in valid:
                    continue
                kickoff, sides = valid[event_id]
                (event,) = item["competitions"]
                names = {team["homeAway"]: team["team"]["displayName"] for team in event["competitors"]}
                if kickoff == utc(fixture["kickoff_at"]) and names == fixture["names"]:
                    candidates.append((event_id, kickoff, sides, event))
            if len(candidates) != 1:
                continue
            event_id, kickoff, sides, event = candidates[0]
            evidence = records[event_id]["source"]
            url = f"{ESPN}/{competition}/summary?event={event_id}"
            raw_summary, stamp = archive._load(evidence, url)
            fields = summary(raw_summary, stamp, event_id, kickoff, sides)
            fixture["espn_event_id"] = event_id
            fixture["espn_identity_evidence"] = board
            fixture["lineup_evidence"] = ({"source": evidence, "scope": "PREGAME_ROSTER_PAYLOAD"}
                                          if fields["roster_payload_observed"] else None)
            fixture["odds_evidence"] = market_quotes(event.get("odds"), board, kickoff.isoformat()) or None



def alternate_context(manifest, cache_root):
    root = cache_root / "alternate-calendars"
    day = dt.date.fromisoformat(manifest["day"])
    context, issues = {}, {}
    for league, evidence in manifest.get("alternate_calendar_evidence", {}).items():
        try:
            expected = ALTERNATE_CALENDARS[league][0]
            if evidence["url"] != expected or evidence["final_url"] != expected:
                raise ValueError("Unexpected alternate calendar URL")
            checked(expected)
            context[league] = calendar_fixtures(league, read_evidence(root, evidence), evidence, day)
        except (OSError, KeyError, ValueError) as exc:
            issues[league] = str(exc)
    if manifest.get("pfl_prematch_issue"):
        issues["pfl"] = manifest["pfl_prematch_issue"]
    for fixture in manifest.get("pfl_prematch_matches", []):
        try:
            from run_ex_pfl_discovery import context_fixture, match_plan, roster_context
            league_id = fixture["official_league_id"]
            source = fixture["calendar_evidence"]
            url = source["final_url"]
            query = f"https://pfl.az/api/v1/tours/get-games?league_id={league_id}"
            page = url.removeprefix(query + "&page=") if url != query else "1"
            if (not page.isascii() or not page.isdigit() or not 1 <= int(page) <= 40
                    or (url != query and url != query + f"&page={page}")):
                raise ValueError("Unrecognized PFL calendar page")
            board = cache_root / "pfl-pregame" / f"league-{league_id}-page-{page}"
            observed = match_plan(json.loads(read_evidence(board, source)), league_id, source)
            match = next((row for row in observed if row["official_match_id"] == fixture["official_match_id"]), None)
            at = utc(fixture["kickoff_at"])
            if (not match or any(match[key] != fixture[key] for key in match)
                    or fixture["status"] != 0 or at.date() != day or utc(source["captured_at"]) >= at):
                raise ValueError("PFL fixture does not match archived board or kickoff")
            verified = context_fixture(match)
            if fixture.get("roster_observation"):
                meta = fixture["roster_observation"]["source"]
                if meta["url"] != verified["official_match_url"] or meta["final_url"] != meta["url"]:
                    raise ValueError("Unrecognized PFL squad evidence URL")
                raw = read_evidence(cache_root / "pfl-pregame" / f'detail-{match["official_match_id"]}', meta)
                verified["roster_observation"] = roster_context(match, json.loads(raw)["data"], meta)
            context.setdefault("az.1", []).append(verified)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            issues["pfl"] = str(exc)
    try:
        bind_espn_context(context, manifest.get("reports", {}), cache_root, day)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        issues["espn_crosswalk"] = str(exc)
    return context, issues


OFFICIAL_RESULT_HOSTS = {
    "de.1": {"www.bundesliga.com", "www.dfb.de"}, "de.2": {"www.bundesliga.com", "www.dfb.de"},
    "en.1": {"www.premierleague.com", "fantasy.premierleague.com"}, "en.2": {"www.efl.com"},
    "es.1": {"www.laliga.com"}, "it.1": {"www.legaseriea.it", "en.legaseriea.it"}, "fr.1": {"ligue1.com", "www.ligue1.com", "www.om.fr"},
    "nl.1": {"eredivisie.nl", "www.eredivisie.nl", "www.knvb.nl"},
    "nl.2": {"keukenkampioendivisie.nl", "www.keukenkampioendivisie.nl", "www.knvb.nl"}, "pt.1": {"www.ligaportugal.pt", "ligaportugal.pt"},
    "be.1": {"www.proleague.be", "proleague.be"}, "tr.1": {"www.tff.org", "tff.org"},
    "no.1": {"www.eliteserien.no", "eliteserien.no"}, "at.1": {"www.bundesliga.at", "bundesliga.at"},
    "gr.1": {"www.slgr.gr", "slgr.gr"}, "UCL": {"www.uefa.com"}, "cz.1": {"www.chanceliga.cz"}, "sk.1": {"www.nikeliga.sk"},
    "ua.1": {"upl.ua", "www.upl.ua"}, "az.1": {"pfl.az", "www.pfl.az"},
}


def read_forecast_pack(receipt):
    metadata = json.loads(receipt.read_text())
    if metadata.get("name") != "ex-prospective-forecasts":
        raise ValueError("Unexpected artifact receipt")
    paths = [path for path in (receipt.parent / "forecasts.jsonl",
                               receipt.parent / "forecasts/forecasts.jsonl") if path.is_file()]
    if len(paths) != 1:
        raise ValueError("Exactly one forecast ledger is required in the artifact")
    raw = paths[0].read_bytes()
    return utc(metadata["created_at"]), read_rows(raw) if raw.strip() else []


def combine_forecasts(packs):
    chosen = {}
    for sealed_at, rows in sorted(packs, key=lambda pack: pack[0]):
        for source in rows:
            row = {**source, "sealed_at": sealed_at.isoformat()}
            event = row["event_id"]
            if not utc(row["forecast_at"]) <= sealed_at < utc(row["kickoff"]):
                raise ValueError("Forecast artifact was not sealed before kickoff")
            older = chosen.get(event)
            if older and (older["league"], older["teams"], utc(older["kickoff"])) != (
                    row["league"], row["teams"], utc(row["kickoff"])):
                raise ValueError("Fixture identity changed across forecast artifacts")
            if older and older["sealed_at"] == row["sealed_at"] and older != row:
                raise ValueError("Conflicting forecasts sealed at the same instant")
            chosen.setdefault(event, row)
    return list(chosen.values())


def archived_belgian_links(manifest, cache, cutoff):
    metadata = manifest.get("belgian_calendar")
    if not metadata:
        return {}
    raw, stamp = cache._load(metadata, BELGIUM_CALENDAR)
    if stamp >= cutoff:
        return {}
    return belgian_links(raw, stamp)


def read_tracked_fixtures(packs, forecast_ids):
    """Track matches from sealed pregame boards even if summaries failed."""
    tracked = {}
    for receipt in sorted(packs.glob("*/receipt.json")):
        candidates = [receipt.parent / name for name in ("forecasts/capture.json", "capture.json")]
        manifest_file = next((path for path in candidates if path.is_file()), None)
        if manifest_file is None:
            continue
        sealed = utc(json.loads(receipt.read_text())["created_at"])
        manifest = json.loads(manifest_file.read_text())
        cache = HistoryArchive(receipt.parent / "pregame-cache", 0)
        day = dt.date.fromisoformat(manifest["day"])
        belgian = archived_belgian_links(manifest, cache, sealed)
        for league, report in manifest["reports"].items():
            competition = ESPN_LEAGUES[league]
            url = f"{ESPN}/{competition}/scoreboard?dates={day:%Y%m%d}"
            raw, captured = cache._load(report["board"], url)
            pregame = {event: (kickoff, sides) for event, kickoff, sides in
                       prematch_fixtures(raw, captured, day, competition, dt.timedelta(hours=48))}
            for record in json.loads(raw)["events"]:
                event = record["id"]
                if event in forecast_ids or event not in pregame:
                    continue
                kickoff, sides = pregame[event]
                if not captured <= sealed < kickoff:
                    continue
                season, _ = observed_season(competition, kickoff, record.get("season", {}).get("year"))
                if type(season) is not int:
                    continue
                match, = record["competitions"]
                row = {"event_id": event, "kickoff": kickoff.isoformat(), "league": league,
                       "teams": sides, "season": season,
                       "names": {side["homeAway"]: side["team"]["displayName"] for side in match["competitors"]},
                       "forecast_at": captured.isoformat(), "sealed_at": sealed.isoformat(),
                       "kind": "PREMATCH_TRACKED_FIXTURE"}
                if league == "be.1":
                    row["official_match_url"] = belgian_match_hint(belgian, kickoff, row["names"])
                old = tracked.get(event)
                if old and any(row[field] != old[field] for field in ("kickoff", "league", "teams", "season")):
                    raise ValueError("Tracked fixture identity changed across archived packs")
                tracked.setdefault(event, row)
    return list(tracked.values())


def settle(forecasts, archive, sealed_at, official, *, expected_kind="PROSPECTIVE_VENUE5_RESEARCH"):
    officer = {}
    for row in official:
        key = row["league"], row["date"], row["home"], row["away"]
        if key in officer:
            raise ValueError("Duplicate official fixture review")
        officer[key] = row
    corroborated, provisional, pending = [], [], []
    for row in forecasts:
        event_id, kickoff = row["event_id"], utc(row["kickoff"])
        sealed = sealed_at if sealed_at is not None else utc(row["sealed_at"])
        if row["kind"] != expected_kind or not utc(row["forecast_at"]) <= sealed < kickoff:
            raise ValueError("Forecast artifact was not sealed before kickoff")
        if archive.clock() < kickoff + dt.timedelta(minutes=90):
            pending.append({"event_id": event_id, "reason": "AWAITING_FULL_TIME"})
            continue
        competition = ESPN_LEAGUES[row["league"]]
        url = f"{ESPN}/{competition}/summary?event={event_id}"
        fixture = {"event_id": event_id, "kickoff_at": row["kickoff"], "teams": row["teams"],
                   "competition": competition, "source_season": row["season"]}

        def parse(raw, captured):
            match_detail(raw, captured, fixture)
            return settled_facts(json.loads(raw), fixture, captured.isoformat())

        try:
            facts, meta = archive.get(url, parse, reusable=lambda r: r["score"] is not None)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            pending.append({"event_id": event_id, **source_error("settled_result", url, exc)})
            continue
        if facts["score"] is None:
            pending.append({"event_id": event_id, "reason": "AWAITING_REGULATION_RESULT"})
            continue
        outcome = {"event_id": event_id, "kickoff": row["kickoff"], "teams": row["teams"],
                   "finished": facts["finished"].isoformat(), "settled_at": meta["retrieved_at"],
                   "league": row["league"], "season": row["season"],
                   "score": facts["score"], "labels": market_labels(*facts["score"]), "source": meta}
        review = officer.get((row["league"], kickoff.date().isoformat(), row["names"]["home"], row["names"]["away"]))
        if review is None:
            provisional.append(outcome)
        elif tuple(review["score"]) != facts["score"]:
            pending.append({"event_id": event_id, "reason": "OFFICIAL_SCORE_CONFLICT", "official": review})
        elif (urlsplit(review["source"]).scheme == "https" and urlsplit(review["source"]).hostname
              and urlsplit(review["source"]).netloc in OFFICIAL_RESULT_HOSTS.get(row["league"], ())
              and utc(review["verified_at"]) >= facts["finished"] and utc(review["verified_at"]) <= archive.clock()
              and review.get("scope") == "REVIEWED_OFFICIAL_RESULT"):
            corroborated.append({**outcome, "official_review": review})
        else:
            provisional.append(outcome)
    return corroborated, provisional, pending


def archive_history(packs, facts, cutoff, *, verified_outcomes=None, conflicts=None):
    """Reuse verified final scores whose evidence was available at forecast time."""
    history = {fact["event_id"]: fact for fact in facts}
    reused = set()
    for pack in sorted(packs.glob("*/receipt.json")):
        ledgers = [pack.parent / "settlement" / name for name in
                   ("outcomes.jsonl", "tracked-verified-outcomes.jsonl")]
        if not any(path.is_file() for path in ledgers):
            continue
        store = HistoryArchive(pack.parent / "settlement-cache", 0, clock=lambda: cutoff)
        sealed = utc(json.loads(pack.read_text())["created_at"])
        if sealed >= cutoff:
            continue
        lines = (line for path in ledgers if path.is_file() for line in path.read_text().splitlines())
        for line in lines:
            row = json.loads(line)
            event_id = row["event_id"]
            if conflicts is not None and event_id in conflicts:
                continue
            try:
                competition = ESPN_LEAGUES[row["league"]]
                review = row["official_review"]
                meta = row["source"]
                source = urlsplit(review["source"])
                evidence_times = [utc(item["retrieved_at"]) for item in review.get("evidence", [])]
                if max(utc(review["verified_at"]), utc(meta["retrieved_at"]), *evidence_times) > sealed:
                    raise ValueError("Archived result evidence postdates the receipt")
                available_at = sealed
                if (source.scheme != "https" or source.netloc not in OFFICIAL_RESULT_HOSTS.get(row["league"], ())
                        or review["scope"] != "REVIEWED_OFFICIAL_RESULT"
                        or review["league"] != row["league"] or review["score"] != row["score"]):
                    raise ValueError("Unverified official settlement evidence")
                event = row["event_id"]
                fixture = {"event_id": event, "kickoff_at": row["kickoff"], "teams": row["teams"],
                           "competition": competition, "source_season": row["season"]}
                for evidence in review.get("evidence", []):
                    store._load(evidence, evidence["url"])
                raw, captured = store._load(meta, f"{ESPN}/{competition}/summary?event={event}")
                detail = match_detail(raw, captured, fixture)
                fact = settled_facts(json.loads(raw), fixture, captured.isoformat())
                if (fact["score"] != tuple(row["score"]) or not fact["finished"]
                        or fact["finished"] > utc(review["verified_at"])):
                    raise ValueError("Archived settlement disagrees with source")
                if row["labels"] != market_labels(*fact["score"]):
                    raise ValueError("Archived settlement labels disagree with source")
                existing = history.get(event)
                if existing and (any(existing[key] != fact[key] for key in ("kickoff", "teams", "competition"))
                                 or (existing["score"] is not None and existing["score"] != fact["score"])):
                    raise ValueError("Conflicting archived result")
                if verified_outcomes is not None:
                    old = verified_outcomes.get(event)
                    if old is None or available_at < old[0]:
                        verified_outcomes[event] = (available_at, row, store)
                if not existing or existing["score"] is None or existing["captured_at"] > available_at:
                    history[event] = {**fact, "captured_at": available_at,
                                      "minutes": validated_team_minutes(detail, fact["teams"].values()),
                                      "source_sha256": meta["sha256"]}
                    reused.add(event)
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                if conflicts is None:
                    raise
                conflicts.add(event_id)
                history.pop(event_id, None)
                reused.discard(event_id)
    return list(history.values()), len(reused)


def component_audit(rows):
    counts = {market: dict.fromkeys(WEIGHTS, 0) for market in MARKETS}
    samples = {market: [] for market in MARKETS}
    for row in rows:
        for market in MARKETS:
            evidence = row.get("components", {}).get(market, {})
            assessed = weighted_evidence(evidence, as_of=row["forecast_at"])
            for component in WEIGHTS:
                counts[market][component] += component in assessed.get("contributions", {})
            if assessed["status"] == "EVIDENCE_COMPLETE_UNCALIBRATED":
                samples[market].append((utc(row["kickoff"]).date(), row["short"][market], row["labels"][market],
                                        tuple(assessed["contributions"][key] for key in WEIGHTS)))
    estimates = {market: compare_calibration(sorted(samples[market])) for market in MARKETS}
    return {"component_coverage": counts, "complete_weighted_rows": {k: len(v) for k, v in samples.items()},
            "chronological_component_research": estimates, "production_allowed": False}


def select_evaluation_rows(model, rows, design=None):
    """Choose the frozen model's cohort from a settlement ledger that spans dates."""
    boundary = max(utc(model["original_last_kickoff"]), utc(model["frozen_at"]))
    original = set(model["original_ids"])
    start = utc(design["holdout_start"]) if design else boundary
    end = utc(design["holdout_end"]) if design else None
    if design and not utc(design["registered_at"]) <= start < end:
        raise ValueError("Invalid preregistered test window")
    return [row for row in rows if row["event_id"] not in original
            and utc(row["forecast_at"]) >= max(boundary, start)
            and utc(row["kickoff"]) > boundary
            and (end is None or utc(row["kickoff"]) < end)]



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--daily-capture")
    parser.add_argument("--component-research", action="store_true")
    parser.add_argument("--prior-pregame", type=Path)
    parser.add_argument("--domestic-packs", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--historical-facts", type=Path)
    parser.add_argument("--export-facts", type=Path)
    parser.add_argument("--prior-settlements", type=Path)
    parser.add_argument("--weekly-scoreboards", type=Path)
    parser.add_argument("--forecast-ledger", type=Path)
    parser.add_argument("--sealed-at")
    parser.add_argument("--packs", type=Path, help="Directory containing individually verified GitHub artifact receipts")
    parser.add_argument("--official", type=Path)
    parser.add_argument("--auto-official", action="store_true")
    parser.add_argument("--frozen-model", type=Path)
    parser.add_argument("--design", type=Path)
    args = parser.parse_args()
    current = dt.datetime.now(dt.timezone.utc)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.daily_capture:
        from run_ex_prematch_archive import collect_registered, seed_recent_pregame
        from ex_leagues import APPROVED_LEAGUES

        day = dt.date.fromisoformat(args.daily_capture)
        if not current.date() <= day <= current.date() + dt.timedelta(days=2):
            parser.error("Choose an upcoming UTC date within two days")
        args.capture = args.output_dir / "capture.json"
        daily_archive = HistoryArchive(args.cache, 26 * len(APPROVED_LEAGUES), fetch=paced_download(.75))
        if args.prior_pregame:
            seed_recent_pregame(args.prior_pregame, daily_archive, day)
        live = collect_registered(daily_archive, day, 25, APPROVED_LEAGUES)
        live["cache_hits"] = daily_archive.cache_hits
        if live["reports"].get("be.1", {}).get("eligible"):
            calendar_cache = HistoryArchive(args.cache, 1, fetch=paced_download(.75))
            try:
                _, live["belgian_calendar"] = calendar_cache.get(
                    BELGIUM_CALENDAR, belgian_links, max_age=dt.timedelta(hours=6))
            except (OSError, ValueError, TypeError, KeyError) as exc:
                live["errors"].append({"league": "be.1", **source_error("official_fixture_links", BELGIUM_CALENDAR, exc)})
        atomic_write(args.capture, json.dumps(live).encode())
    if args.capture:
        if args.forecast_ledger or (not args.historical_facts and (not args.plan or not args.history)):
            parser.error("Capture mode requires archived facts or raw history and its plan")
        if args.historical_facts:
            facts, missing = portable_facts(args.historical_facts), 0
        else:
            facts, missing = load_facts(json.loads(args.plan.read_text()), args.history)
        if not facts or missing:
            raise ValueError("Incomplete historical archive")
        if args.export_facts and not args.historical_facts:
            payload = [dict(row, **{field: row[field].isoformat() if row[field] is not None else None
                                   for field in ("kickoff", "captured_at", "finished")}) for row in facts]
            atomic_write(args.export_facts, jsonl(payload))
        manifest = json.loads(args.capture.read_text())
        archive = HistoryArchive(args.cache, 0)
        model, weather, weather_errors = None, {}, {}
        if args.component_research:
            from ex_research_components import audit
            from ex_history_environment import coordinates
            from ex_pregame_weather import forecast

            model = audit(facts)
            atomic_write(args.output_dir / "component-research-audit.json",
                         (json.dumps(model, indent=2) + "\n").encode())
            registry = json.loads(Path("config/ex_history_venues.json").read_text())
            registry.update(json.loads(Path("config/ex_pregame_venues.json").read_text()))
            weather_archive = HistoryArchive(args.cache, 25, fetch=paced_download(.75))
            for league, report in manifest["reports"].items():
                for record in report["records"]:
                    event = record["event_id"]
                    try:
                        url = f"{ESPN}/{ESPN_LEAGUES[league]}/summary?event={event}"
                        raw, stamp = archive._load(record["source"], url)
                        kickoff = utc(record["kickoff_at"])
                        summary(raw, stamp, event, kickoff, record["teams"])
                        venue = (json.loads(raw).get("gameInfo") or {}).get("venue")
                        point = coordinates(venue, registry)
                        if point is None:
                            weather_errors[event] = {"category": "VENUE_COORDINATES_UNVERIFIED"}
                            continue
                        item = forecast(weather_archive, point, kickoff.isoformat(),
                                        lambda: archive.clock().isoformat())
                        weather[event] = {**item, "venue_source": registry[str(venue["id"])]["source"]}
                    except (OSError, ValueError, TypeError, KeyError, AttributeError, BudgetExhausted) as exc:
                        weather_errors[event] = source_error("research_weather", None, exc)
        # Establish the cutoff after all source acquisition and integrity verification.
        cutoff = archive.clock()
        reused = 0
        history_conflicts = set()
        if args.prior_settlements:
            facts, reused = archive_history(args.prior_settlements, facts, cutoff, conflicts=history_conflicts)
        daily = []
        domestic = None
        if args.domestic_packs:
            receipts = sorted(args.domestic_packs.glob("*/receipt.json"), key=lambda path: int(path.parent.name))
            candidates = [path for path in receipts if utc(json.loads(path.read_text())["created_at"]) < cutoff]
            if candidates:
                domestic = domestic_snapshot(candidates[-1].parent)
        rolling = []
        if args.weekly_scoreboards:
            existing = {r["event_id"]: r for r in facts}
            for row in scoreboard_facts(args.weekly_scoreboards, cutoff, conflicts=history_conflicts):
                event = row["event_id"]
                prior = existing.get(event)
                if prior and (any(prior[key] != row[key] for key in ("teams", "competition", "kickoff"))
                              or (prior["score"] is not None and prior["score"] != row["score"])):
                    history_conflicts.add(event)
                elif prior is None:
                    rolling.append(row)
            facts = [row for row in facts + rolling if row["event_id"] not in history_conflicts]
        forecasts, skipped = forecast_rows(manifest, archive, facts, cutoff, daily=daily, domestic=domestic, component_model=model, weather=weather)
        atomic_write(args.output_dir / "daily-analysis.json", (json.dumps(daily, indent=2) + "\n").encode())
        if any(archive.clock() >= utc(row["fixture"]["kickoff_at"]) for row in daily):
            raise ValueError("Forecast execution finished past kickoff")
        atomic_write(args.output_dir / "forecasts.jsonl", jsonl(forecasts))
        context, issues = alternate_context(manifest, args.cache)
        atomic_write(args.output_dir / "official-fixture-context.json",
                     (json.dumps(context, ensure_ascii=False, indent=2) + "\n").encode())
        report = {"forecasts": len(forecasts), "historical_matches": len(facts),
                  "reused_verified_outcomes": reused, "rolling_scoreboard_matches": len(rolling), "skipped": skipped,
                  "daily_fixture_records": len(daily),
                  "domestic_source_coverage": domestic[1] if domestic else [],
                  "domestic_baselines": sum(bool((row["domestic_research"] or {}).get("baseline")) for row in daily),
                  "daily_research_covered": sum(row["venue5_research"] is not None or
                                                bool((row["domestic_research"] or {}).get("baseline")) for row in daily),
                  "historical_events_quarantined": sorted(history_conflicts),
                  "weather_sources_observed": len(weather), "weather_errors": weather_errors,
                  "capture_source_errors": manifest.get("errors", []),
                  "capture_cache_hits": manifest.get("cache_hits", 0),
                  "capture_network_requests": manifest.get("requests"),
                  "alternate_fixtures": {league: len(rows) for league, rows in context.items()},
                  "alternate_calendar_issues": issues}
    else:
        if args.packs:
            if args.forecast_ledger or args.sealed_at:
                parser.error("Use packs or a single forecast ledger")
            packs = [read_forecast_pack(receipt) for receipt in sorted(args.packs.glob("*/receipt.json"))]
            if not packs:
                raise ValueError("No forecast artifact receipts")
            forecasts, sealed = combine_forecasts(packs), None
        else:
            if not args.forecast_ledger or not args.sealed_at:
                parser.error("Settlement mode requires a forecast ledger and artifact creation time")
            raw = args.forecast_ledger.read_bytes()
            forecasts, sealed = (read_rows(raw) if raw.strip() else []), utc(args.sealed_at)
        tracked = read_tracked_fixtures(args.packs, {r["event_id"] for r in forecasts}) if args.packs else []
        verified_archive = {}
        if args.prior_settlements:
            archive_history(args.prior_settlements, [], current, verified_outcomes=verified_archive)

        def reuse(matches):
            old, queued = [], []
            for fixture in matches:
                entry = verified_archive.get(fixture["event_id"])
                if entry is None:
                    queued.append(fixture)
                    continue
                _, row, store = entry
                if (row["league"] != fixture["league"] or row["teams"] != fixture["teams"]
                        or utc(row["kickoff"]) != utc(fixture["kickoff"])):
                    raise ValueError("Archived result and forecast identity disagree")
                for meta in [row["source"], *row["official_review"].get("evidence", [])]:
                    raw, _ = store._load(meta, meta["url"])
                    atomic_write(args.cache / "raw" / meta["sha256"], raw)
                old.append(row)
            return queued, old

        queued_forecasts, prior_forecasts = reuse(forecasts)
        queued_tracked, prior_tracked = reuse(tracked)
        official = json.loads(args.official.read_text()) if args.official else []
        # Official sources and primary score results have separate request budgets.
        fetch = paced_download(.75)
        result_archive = HistoryArchive(args.cache, len(queued_forecasts) + len(queued_tracked), fetch=fetch)
        official_errors = []
        if args.auto_official:
            official_archive = HistoryArchive(args.cache, 32, fetch=fetch)
            found, official_errors = league_reviews(queued_forecasts + queued_tracked, official_archive)
            known = {(r["league"], r["date"], r["home"], r["away"]) for r in official}
            official.extend(r for r in found if (r["league"], r["date"], r["home"], r["away"]) not in known)
        corroborated, provisional, pending = settle(
            queued_forecasts, result_archive,
            sealed, official,
        )
        verified_tracking, provisional_tracking, pending_tracking = settle(
            queued_tracked, result_archive, None, official, expected_kind="PREMATCH_TRACKED_FIXTURE",
        )
        corroborated = prior_forecasts + corroborated
        verified_tracking = prior_tracked + verified_tracking
        atomic_write(args.output_dir / "tracked-verified-outcomes.jsonl", jsonl(verified_tracking))
        atomic_write(args.output_dir / "tracked-provisional-outcomes.jsonl", jsonl(provisional_tracking))
        atomic_write(args.output_dir / "outcomes.jsonl", jsonl(corroborated))
        atomic_write(args.output_dir / "provisional-outcomes.jsonl", jsonl(provisional))
        rows = join_holdout(forecasts, corroborated) if corroborated else []
        model = json.loads(args.frozen_model.read_text()) if args.frozen_model else None
        design = json.loads(args.design.read_text()) if args.design else None
        cohort = select_evaluation_rows(model, rows, design) if model else []
        report = {"corroborated": len(rows), "provisional": len(provisional), "pending": pending,
                  "official_source_errors": official_errors,
                  "verified_outcomes_reused": len(prior_forecasts) + len(prior_tracked),
                  "new_primary_requests": result_archive.requests,
                  "fixture_result_tracking": {"verified": len(verified_tracking),
                                              "provisional": len(provisional_tracking),
                                              "pending": pending_tracking},
                  "eligible_evaluation_rows": len(cohort),
                  "components": component_audit(rows),
                  "evaluation": evaluate(model, cohort, design, evaluation_at=current) if cohort else {"status": "NO_ELIGIBLE_HOLDOUT"}}
    report.update({"generated_at": current.isoformat(), "production_allowed": False, "ex_final_allowed": False})
    atomic_write(args.output_dir / "report.json", (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
