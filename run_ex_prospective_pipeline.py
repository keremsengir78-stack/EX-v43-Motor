"""Create and settle a prospective research ledger using immutable archive inputs."""

import argparse
import datetime as dt
import json
from pathlib import Path
from statistics import mean
from urllib.parse import urlsplit

from ex_decision import MARKETS, WEIGHTS, weighted_evidence
from ex_espn_provider import ESPN_LEAGUES
from ex_historical_features import market_labels
from ex_history_archive import HistoryArchive, atomic_write, paced_download, source_error, utc
from ex_history_sources import ESPN, match_detail, teams
from ex_model_challengers import compare_calibration
from ex_official_calendar import calendar_fixtures
from run_ex_official_sources import ALTERNATE_CALENDARS, checked, read_evidence
from ex_retrospective import observed_season, settled_facts, window, workload
from run_ex_prematch_archive import prematch_fixtures, summary
from run_ucl_matchday_inputs import market_quotes
from run_ex_prospective_validation import evaluate, join_holdout, read_rows
from run_ex_retrospective import load_facts


def jsonl(rows):
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode()


def forecast_rows(manifest, cache, facts, now):
    available = [fact for fact in facts if fact["score"] is not None and fact["finished"]
                 and fact["finished"] <= fact["captured_at"] < now]
    labels = {row["event_id"]: market_labels(*row["score"]) for row in available}
    rows, skipped = [], []
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
            summary(raw, captured, event_id, kickoff, fixture["teams"])
            season, season_basis = observed_season(competition, kickoff, event.get("season", {}).get("year"))
            if not max(captured, board_at) < now < kickoff or type(season) is not int:
                skipped.append({"event_id": event_id, "reason": "TIME_OR_SEASON_UNAVAILABLE"})
                continue
            teams_features = []
            for side in ("home", "away"):
                club = fixture["teams"][side]
                history = [{**row, "index_team": club} for row in available if club in row["teams"].values()
                           and row["event_id"] != event_id and row["finished"] < now]
                league_rows = [(row["kickoff"], "home" if row["teams"]["home"] == club else "away", row)
                               for row in history if row["competition"] == competition]
                short, strength = window(sorted(league_rows, key=lambda row: row[0]), labels, side, season)
                context, minutes = workload(history, kickoff)
                teams_features.append((short, strength, context, minutes))
            home, away = teams_features
            if not home[0] or not away[0]:
                skipped.append({"event_id": event_id, "reason": "VENUE5_HISTORY_INCOMPLETE"})
                continue
            players = {side["homeAway"]: side["team"]["displayName"] for side in match["competitors"]}
            rows.append({"event_id": event_id, "kickoff": kickoff.isoformat(), "forecast_at": now.isoformat(),
                         "league": league, "season": season, "season_basis": season_basis, "teams": fixture["teams"], "names": players,
                         "short": {m: mean((home[0][m], away[0][m])) for m in MARKETS},
                         "strength": {m: mean((home[1][m], away[1][m])) for m in MARKETS}
                         if home[1] and away[1] else None,
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
    "en.1": {"www.premierleague.com"}, "en.2": {"www.efl.com"},
    "es.1": {"www.laliga.com"}, "it.1": {"www.legaseriea.it"}, "fr.1": {"ligue1.com", "www.ligue1.com"},
    "nl.1": {"eredivisie.nl", "www.eredivisie.nl"},
    "nl.2": {"keukenkampioendivisie.nl", "www.keukenkampioendivisie.nl"}, "pt.1": {"www.ligaportugal.pt", "ligaportugal.pt"},
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


def settle(forecasts, archive, sealed_at, official):
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
        if row["kind"] != "PROSPECTIVE_VENUE5_RESEARCH" or not utc(row["forecast_at"]) <= sealed < kickoff:
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


def archive_history(packs, facts, cutoff):
    """Reuse verified final scores whose evidence was available at forecast time."""
    history = {fact["event_id"]: fact for fact in facts}
    reused = set()
    for pack in sorted(packs.glob("*/receipt.json")):
        ledger = pack.parent / "settlement/outcomes.jsonl"
        if not ledger.is_file():
            continue
        store = HistoryArchive(pack.parent / "settlement-cache", 0)
        sealed = utc(json.loads(pack.read_text())["created_at"])
        for line in ledger.read_text().splitlines():
            row = json.loads(line)
            competition = ESPN_LEAGUES[row["league"]]
            review = row["official_review"]
            meta = row["source"]
            source = urlsplit(review["source"])
            available_at = max(utc(review["verified_at"]), utc(meta["retrieved_at"]), sealed)
            if available_at >= cutoff:
                continue
            if (source.scheme != "https" or source.netloc not in OFFICIAL_RESULT_HOSTS.get(row["league"], ())
                    or review["scope"] != "REVIEWED_OFFICIAL_RESULT"
                    or review["league"] != row["league"] or review["score"] != row["score"]):
                raise ValueError("Unverified official settlement evidence")
            event = row["event_id"]
            fixture = {"event_id": event, "kickoff_at": row["kickoff"], "teams": row["teams"],
                       "competition": competition, "source_season": row["season"]}
            raw, captured = store._load(meta, f"{ESPN}/{competition}/summary?event={event}")
            match_detail(raw, captured, fixture)
            fact = settled_facts(json.loads(raw), fixture, captured.isoformat())
            if (fact["score"] != tuple(row["score"]) or not fact["finished"]
                    or fact["finished"] > utc(review["verified_at"])):
                raise ValueError("Archived settlement disagrees with source")
            existing = history.get(event)
            if existing and any(existing[key] != fact[key] for key in ("score", "kickoff", "teams", "competition")):
                raise ValueError("Conflicting archived result")
            if not existing or existing["captured_at"] > available_at:
                history[event] = {**fact, "captured_at": available_at}
                reused.add(event)
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
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--prior-settlements", type=Path)
    parser.add_argument("--forecast-ledger", type=Path)
    parser.add_argument("--sealed-at")
    parser.add_argument("--packs", type=Path, help="Directory containing individually verified GitHub artifact receipts")
    parser.add_argument("--official", type=Path)
    parser.add_argument("--frozen-model", type=Path)
    parser.add_argument("--design", type=Path)
    args = parser.parse_args()
    current = dt.datetime.now(dt.timezone.utc)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.capture:
        if not args.plan or not args.history or args.forecast_ledger:
            parser.error("Capture mode requires plan and history")
        facts, missing = load_facts(json.loads(args.plan.read_text()), args.history)
        if not facts or missing:
            raise ValueError("Incomplete historical archive")
        manifest = json.loads(args.capture.read_text())
        archive = HistoryArchive(args.cache, 0)
        # Establish the feature cutoff after archive integrity verification.
        cutoff = archive.clock()
        reused = 0
        if args.prior_settlements:
            facts, reused = archive_history(args.prior_settlements, facts, cutoff)
        forecasts, skipped = forecast_rows(manifest, archive, facts, cutoff)
        if any(archive.clock() >= utc(row["kickoff"]) for row in forecasts):
            raise ValueError("Forecast execution finished past kickoff")
        atomic_write(args.output_dir / "forecasts.jsonl", jsonl(forecasts))
        context, issues = alternate_context(manifest, args.cache)
        atomic_write(args.output_dir / "official-fixture-context.json",
                     (json.dumps(context, ensure_ascii=False, indent=2) + "\n").encode())
        report = {"forecasts": len(forecasts), "historical_matches": len(facts),
                  "reused_verified_outcomes": reused, "skipped": skipped,
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
        official = json.loads(args.official.read_text()) if args.official else []
        corroborated, provisional, pending = settle(
            forecasts, HistoryArchive(args.cache, len(forecasts), fetch=paced_download(.75)),
            sealed, official,
        )
        atomic_write(args.output_dir / "outcomes.jsonl", jsonl(corroborated))
        atomic_write(args.output_dir / "provisional-outcomes.jsonl", jsonl(provisional))
        rows = join_holdout(forecasts, corroborated) if corroborated else []
        model = json.loads(args.frozen_model.read_text()) if args.frozen_model else None
        design = json.loads(args.design.read_text()) if args.design else None
        cohort = select_evaluation_rows(model, rows, design) if model else []
        report = {"corroborated": len(rows), "provisional": len(provisional), "pending": pending,
                  "eligible_evaluation_rows": len(cohort),
                  "components": component_audit(rows),
                  "evaluation": evaluate(model, cohort, design, evaluation_at=current) if cohort else {"status": "NO_ELIGIBLE_HOLDOUT"}}
    report.update({"generated_at": current.isoformat(), "production_allowed": False, "ex_final_allowed": False})
    atomic_write(args.output_dir / "report.json", (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
