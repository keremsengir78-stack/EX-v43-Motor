"""Audit archived official scores and sealed prospective forecasts without recalculation."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from urllib.parse import urlsplit

from ex_daily_official import key
from ex_daily_research import rolling_domestic
from ex_ucl_baseline import cross_league_baseline
from ex_rolling_scoreboards import archived_domestic_boards, scoreboard_facts
from ex_evidence_store import restore
from ex_espn_provider import ESPN_LEAGUES
from ex_history_archive import atomic_write, utc
from ex_leagues import APPROVED_LEAGUES
from run_ex_official_queue_join import source_rows
from run_ex_prospective_pipeline import (OFFICIAL_RESULT_HOSTS, archive_history, combine_forecasts,
                                         portable_facts, read_forecast_pack, select_evaluation_rows)
from run_ex_prospective_validation import evaluate, join_holdout


def compare_results(facts, fixtures, secondary):
    """Require unique, oriented team IDs, exact kickoff and a distinct official publication."""
    names = defaultdict(set)
    for row in fixtures:
        home, away = key(row["league"], "", *[row["names"][side] for side in ("home", "away")])[2:]
        for label, side in ((home, "home"), (away, "away")):
            names[row["league"], label].add(row["teams"][side])
    leagues = {ESPN_LEAGUES[league]: league for league in APPROVED_LEAGUES}
    indexed = defaultdict(list)
    for fact in facts:
        indexed[leagues.get(fact["competition"]), fact["kickoff"],
                fact["teams"]["home"], fact["teams"]["away"]].append(fact)
    stats = {league: Counter() for league in APPROVED_LEAGUES}
    matched, conflicts, seen = {}, set(), set()
    for row in secondary:
        league = row["league"]
        if league not in stats:
            continue
        _, _, home, away = key(league, row["date"], row["home"], row["away"])
        fingerprint = league, row.get("kickoff_at"), row["date"], home, away, tuple(row["official_score"])
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        count = stats[league]
        count["distinct_official_rows"] += 1
        evidence = row["raw_evidence"]
        url = urlsplit(evidence["url"])
        if url.scheme != "https" or url.netloc not in OFFICIAL_RESULT_HOSTS.get(league, ()):
            count["unrecognized_origin"] += 1
            continue
        if not row.get("kickoff_at"):
            count["kickoff_unavailable"] += 1
            continue
        kickoff = utc(row["kickoff_at"])
        home_ids, away_ids = names[league, home], names[league, away]
        if len(home_ids) != 1 or len(away_ids) != 1:
            count["team_identity_unavailable_or_ambiguous"] += 1
            continue
        candidates = indexed[league, kickoff, next(iter(home_ids)), next(iter(away_ids))]
        if len(candidates) != 1:
            count["provider_fixture_unavailable_or_ambiguous"] += 1
            continue
        fact, = candidates
        event = fact["event_id"]
        if fact.get("source_sha256") in (None, evidence["sha256"]):
            count["distinct_source_unverified"] += 1
            continue
        if fact["score"] != tuple(row["official_score"]):
            count["score_conflict"] += 1
            conflicts.add(event)
            continue
        if fact["finished"] is None or not kickoff < fact["finished"] or utc(evidence["retrieved_at"]) <= kickoff:
            count["completion_time_unverified"] += 1
            continue
        matched[event] = {"event_id": event, "league": league, "kickoff_at": kickoff.isoformat(),
                          "team_ids": fact["teams"], "score": fact["score"], "provider_sha256": fact["source_sha256"],
                          "official_match_id": row.get("source_match_id"), "official_source": evidence,
                          "official_sealed_at": row.get("official_sealed_at"),
                          "scope": "EXACT_OFFICIAL_SCORE_AGREEMENT_LINEAGE_UNCERTIFIED"}
    return [row for event, row in matched.items() if event not in conflicts], stats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--cutoff", type=utc, required=True)
    parser.add_argument("--target-artifact", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for kind, files in {
        "historical-facts": None, "weekly-capacity": None, "ucl-domestic-research": None, "frozen-candidates": None, "official-source-probe": None,
        "prematch-and-research": {"forecasts/forecasts.jsonl", "forecasts/daily-analysis.json"},
        "settlement-and-performance": None,
    }.items():
        restore(args.store, kind, args.work / kind, files=files)
    facts_path = next((args.work / "historical-facts").glob("*/historical-facts.jsonl"))
    facts = portable_facts(facts_path)
    verified, conflicts = {}, set()
    archive_history(args.work / "settlement-and-performance", facts, args.cutoff,
                    verified_outcomes=verified, conflicts=conflicts)
    forecast_packs, daily, target_daily = [], [], []
    for receipt in (args.work / "prematch-and-research").glob("*/receipt.json"):
        if utc(json.loads(receipt.read_bytes())["created_at"]) >= args.cutoff:
            continue
        reports = receipt.parent / "forecasts"
        if (reports / "forecasts.jsonl").is_file():
            forecast_packs.append(read_forecast_pack(receipt))
        if (reports / "daily-analysis.json").is_file():
            rows = json.loads((reports / "daily-analysis.json").read_bytes())
            daily.extend(rows)
            if receipt.parent.name in args.target_artifact:
                target_daily.extend(rows)
    forecasts = combine_forecasts(forecast_packs)
    fixtures = [*forecasts, *({"league": f["league"], "names": {"home": f["home"], "away": f["away"]},
                               "teams": f["team_ids"]} for row in daily for f in [row["fixture"]])]
    secondary, probe_errors = [], []
    probes = (args.work / "official-source-probe").glob("*/receipt.json")
    for receipt in sorted(probes, key=lambda path: json.loads(path.read_bytes())["created_at"]):
        if utc(json.loads(receipt.read_bytes())["created_at"]) >= args.cutoff:
            continue
        try:
            seal = utc(json.loads(receipt.read_bytes())["created_at"])
            secondary.extend([{**row, "official_sealed_at": seal.isoformat()}
                              for row in source_rows(receipt.parent)
                              if utc(row["raw_evidence"]["retrieved_at"]) <= seal])
        except (OSError, ValueError, TypeError, KeyError) as exc:
            probe_errors.append({"id": receipt.parent.name, "reason": str(exc)})
    matched, counts = compare_results(facts, fixtures, secondary)
    model = json.loads(next((args.work / "frozen-candidates").glob("*/frozen-candidates.json")).read_bytes())
    scoped_forecasts = select_evaluation_rows(model, forecasts)
    joined = join_holdout(scoped_forecasts, [row for _, row, _ in verified.values()]) if (
        set(verified) & {row["event_id"] for row in scoped_forecasts}) else []
    if args.target_artifact and not target_daily:
        raise ValueError("No requested archived target rows")
    checked_targets = target_daily or daily
    original = {row["event_id"]: row for row in facts}
    prior_results = []
    for event, (seal, result, _) in sorted(verified.items()):
        related = []
        for row in checked_targets:
            fixture = row["fixture"]
            if not set(result["teams"].values()) & set(fixture["team_ids"].values()):
                continue
            related.append({"target": fixture["event_id"], "league": fixture["league"],
                            "same_league": fixture["league"] == result["league"],
                            "available_at_target_cutoff": seal < utc(row["as_of"]),
                            "orientation": {side: next(key for key, club in result["teams"].items() if club == team)
                                            for side, team in fixture["team_ids"].items()
                                            if team in result["teams"].values()}})
        primary = original.get(event)
        prior_results.append({"event_id": event, "league": result["league"], "kickoff": result["kickoff"],
                              "teams": result["teams"], "matched_historical_event_id": primary is not None,
                              "shared_team_targets": related, "sealed_at": seal.isoformat()})
    form_candidates = []
    by_cutoff = {}
    primary_receipt = json.loads((facts_path.parent / "receipt.json").read_bytes())
    def replay_book(cutoff):
        if cutoff in by_cutoff:
            return by_cutoff[cutoff]
        collisions = set()
        primary, _ = archive_history(args.work / "settlement-and-performance", facts, cutoff, conflicts=collisions)
        weekly = scoreboard_facts(args.work / "weekly-capacity", cutoff, conflicts=collisions)
        packs = sorted((args.work / "ucl-domestic-research").glob("*/receipt.json"), key=lambda p: int(p.parent.name))
        recent = [p.parent for p in packs if utc(json.loads(p.read_bytes())["created_at"]) < cutoff]
        supplemental = archived_domestic_boards(recent[-1], cutoff, tuple(APPROVED_LEAGUES)) if recent else []
        indexed = {r["event_id"]: r for r in primary}
        for sample in weekly + supplemental:
            old = indexed.get(sample["event_id"])
            if old and (any(old[k] != sample[k] for k in ("teams", "competition", "kickoff"))
                        or (old["score"] is not None and old["score"] != sample["score"])):
                collisions.add(sample["event_id"])
            elif old is None or old["score"] is None:
                indexed[sample["event_id"]] = sample
        book = defaultdict(list)
        for event, sample in indexed.items():
            if event not in collisions:
                for team in sample["teams"].values():
                    book[team].append(sample)
        by_cutoff[cutoff] = book
        return book

    for row in checked_targets:
        baseline = row.get("domestic_research") or {}
        cutoff = utc(row["as_of"])
        diagnostics = {}
        book = replay_book(cutoff)
        replay = rolling_domestic(row["fixture"], book, cutoff, diagnostics=diagnostics)
        replayed = {}
        if replay is not None and baseline.get("history_scope") == "ROLLING_DOMESTIC_PROVIDER_TEAM_ID":
            recalculated = cross_league_baseline(*replay, cutoff_date=cutoff.date().isoformat())
            if recalculated["domestic_leagues"] == baseline["domestic_leagues"]:
                replayed = recalculated["samples"]
        for side, sample in baseline.get("samples", {}).items():
            days = {day for group in sample.get("match_dates", []) for day in group}
            if not days:
                continue
            club = row["fixture"]["team_ids"][side]
            for result in matched:
                if (result["league"] == baseline["domestic_leagues"][side]
                        and club in result["team_ids"].values() and result["kickoff_at"][:10] in days):
                    actual = replayed.get(side, {})
                    groups = [name for i, (name, event_ids) in enumerate(
                        diagnostics.get(side, {}).get("form_sample_event_ids", {}).items())
                        if result["event_id"] in event_ids and actual.get("match_dates")
                        and actual["match_dates"][i] == sample["match_dates"][i]
                        and list(actual["rates"][i]) == sample["rates"][i]
                        and any(fact["event_id"] == result["event_id"]
                                and fact["teams"] == result["team_ids"]
                                and fact["kickoff"] == utc(result["kickoff_at"])
                                and fact["score"] == result["score"]
                                and fact.get("source_sha256") == result["provider_sha256"]
                                for fact in book[club])]
                    form_candidates.append({"target": row["fixture"]["event_id"], "target_fixture": row["fixture"],
                                            "decision_cutoff": row["as_of"], "side": side,
                                            "historical_event": result["event_id"], "historical_fixture": result,
                                            "primary_archive_seal": primary_receipt["created_at"],
                                            "reproduced_form_windows": groups,
                                            "official_observed_before_target_cutoff":
                                                utc(result["official_source"]["retrieved_at"]) < cutoff,
                                            "official_sealed_before_target_cutoff":
                                                utc(result["official_sealed_at"]) < cutoff,
                                            "status": "BLOCKED_SOURCE_LINEAGE_UNPROVEN" if groups
                                                      else "BLOCKED_FORM_MEMBERSHIP_UNVERIFIED"})
    report = {"archive_facts": len(facts), "targets_audited": len(checked_targets), "per_league": counts,
              "official_score_matches": matched, "form_window_date_candidates": form_candidates,
              "probe_errors": probe_errors, "settlement_conflicts": len(conflicts), "archived_independent_results": prior_results,
              "sealed_forecasts": len(forecasts), "frozen_candidate_holdout_examples": len(joined),
              "holdout_iso_weeks": sorted({utc(row["kickoff"]).date().isocalendar()[:2] for row in joined}),
              "holdout_research_evaluation": evaluate(model, joined) if joined else None,
              "archived_acceptances": {blocker: sum(
                  blocker not in market["issues"] for row in checked_targets
                  for market in row["auto_control_by_market"].values())
                  for blocker in ("ingestion:blocked", "second_source:unverified", "context:unverified")},
              "production_allowed": False}
    atomic_write(args.output, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())


if __name__ == "__main__":
    main()
