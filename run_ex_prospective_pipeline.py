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
from ex_retrospective import settled_facts, window, workload
from run_ex_prematch_archive import summary
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
            season = event.get("season", {}).get("year")
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
                         "league": league, "season": season, "teams": fixture["teams"], "names": players,
                         "short": {m: mean((home[0][m], away[0][m])) for m in MARKETS},
                         "strength": {m: mean((home[1][m], away[1][m])) for m in MARKETS}
                         if home[1] and away[1] else None,
                         "observed_context": {"home": home[2], "away": away[2],
                                              "home_minutes": home[3], "away_minutes": away[3]},
                         "source": source, "kind": "PROSPECTIVE_VENUE5_RESEARCH"})
    return rows, skipped


OFFICIAL_RESULT_HOSTS = {
    "de.1": {"www.bundesliga.com", "www.dfb.de"}, "de.2": {"www.bundesliga.com", "www.dfb.de"},
    "en.1": {"www.premierleague.com"}, "en.2": {"www.efl.com"},
    "es.1": {"www.laliga.com"}, "it.1": {"www.legaseriea.it"}, "fr.1": {"ligue1.com", "www.ligue1.com"},
    "UCL": {"www.uefa.com"}, "cz.1": {"www.chanceliga.cz"}, "sk.1": {"www.nikeliga.sk"},
    "ua.1": {"upl.ua", "www.upl.ua"}, "az.1": {"pfl.az", "www.pfl.az"},
}


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
        if row["kind"] != "PROSPECTIVE_VENUE5_RESEARCH" or not utc(row["forecast_at"]) <= sealed_at < kickoff:
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


def component_audit(rows):
    counts = {market: dict.fromkeys(WEIGHTS, 0) for market in MARKETS}
    samples = {market: [] for market in MARKETS}
    for row in rows:
        for market in MARKETS:
            evidence = row.get("components", {}).get(market, {})
            assessed = weighted_evidence(evidence, as_of=row["forecast_at"])
            for component in WEIGHTS:
                counts[market][component] += component in assessed.get("contributions", {})
            if (assessed["status"] == "EVIDENCE_COMPLETE_UNCALIBRATED"
                    and utc(row["kickoff"]).date() == utc(row["finished"]).date()):
                samples[market].append((utc(row["kickoff"]).date(), row["short"][market], row["labels"][market],
                                        tuple(assessed["contributions"][key] for key in WEIGHTS)))
    estimates = {market: compare_calibration(sorted(samples[market])) for market in MARKETS}
    return {"component_coverage": counts, "complete_weighted_rows": {k: len(v) for k, v in samples.items()},
            "chronological_component_research": estimates, "production_allowed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--history", type=Path)
    parser.add_argument("--forecast-ledger", type=Path)
    parser.add_argument("--sealed-at")
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
        forecasts, skipped = forecast_rows(manifest, archive, facts, archive.clock())
        if any(archive.clock() >= utc(row["kickoff"]) for row in forecasts):
            raise ValueError("Forecast execution finished past kickoff")
        atomic_write(args.output_dir / "forecasts.jsonl", jsonl(forecasts))
        report = {"forecasts": len(forecasts), "skipped": skipped}
    else:
        if not args.forecast_ledger or not args.sealed_at:
            parser.error("Settlement mode requires a forecast ledger and artifact creation time")
        raw = args.forecast_ledger.read_bytes()
        forecasts = read_rows(raw) if raw.strip() else []
        official = json.loads(args.official.read_text()) if args.official else []
        corroborated, provisional, pending = settle(
            forecasts, HistoryArchive(args.cache, len(forecasts), fetch=paced_download(.75)),
            utc(args.sealed_at), official,
        )
        atomic_write(args.output_dir / "outcomes.jsonl", jsonl(corroborated))
        atomic_write(args.output_dir / "provisional-outcomes.jsonl", jsonl(provisional))
        rows = join_holdout(forecasts, corroborated) if corroborated else []
        model = json.loads(args.frozen_model.read_text()) if args.frozen_model else None
        design = json.loads(args.design.read_text()) if args.design else None
        report = {"corroborated": len(rows), "provisional": len(provisional), "pending": pending,
                  "components": component_audit(rows),
                  "evaluation": evaluate(model, rows, design, evaluation_at=current) if model and rows else {"status": "NO_ELIGIBLE_HOLDOUT"}}
    report.update({"generated_at": current.isoformat(), "production_allowed": False, "ex_final_allowed": False})
    atomic_write(args.output_dir / "report.json", (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
